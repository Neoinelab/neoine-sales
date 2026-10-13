"""전역 활동 검색 API: 기존 필터와 계획일 범위·정렬·확장 키워드(AC9)."""

from typing import TYPE_CHECKING

import pytest

from tests.e2e.payloads import action_payload, customer_payload, deal_payload

if TYPE_CHECKING:
    from httpx import AsyncClient

DEALS = "/api/v1/deals"
ACTIONS = "/api/v1/deal-actions"
PROBLEM = "application/problem+json"


async def _deal(client: AsyncClient, code: str = "DEAL-001") -> str:
    customer = (await client.post("/api/v1/customers", json=customer_payload())).json()
    response = await client.post(DEALS, json=deal_payload(customer["id"], code=code))
    return str(response.json()["id"])


async def _create(client: AsyncClient, deal_id: str, **overrides: object) -> None:
    response = await client.post(f"{DEALS}/{deal_id}/actions", json=action_payload(**overrides))
    assert response.status_code == 201, response.text


async def _names(client: AsyncClient, **params: str) -> list[str]:
    response = await client.get(ACTIONS, params=params)
    assert response.status_code == 200, response.text
    return [item["action"] for item in response.json()["items"]]


@pytest.fixture
async def seeded(client: AsyncClient) -> str:
    first, second = await _deal(client), await _deal(client, "DEAL-002")
    rows = [
        (first, "킥오프", "meeting", "김영업", "2026-03-01", "일정 협의", "요구사항", "2026-04-10"),
        (
            first,
            "견적 발송",
            "email",
            "박영업",
            "2026-03-02",
            "100% 할인",
            "회신 확인",
            "2026-04-01",
        ),
        (second, "킥오프 2", "meeting", "박영업", "2026-03-03", "", "계약서 초안", "2026-04-10"),
    ]
    for deal_id, action, kind, actor, day, memo, next_action, due in rows:
        await _create(
            client,
            deal_id,
            action=action,
            action_type=kind,
            actor=actor,
            memo=memo,
            next_action=next_action,
            due_date=due,
            acted_at=f"{day}T10:00:00+09:00",
        )
    return second


async def test_global_search_filters(client: AsyncClient, seeded: str) -> None:
    assert set(await _names(client)) == {"킥오프", "견적 발송", "킥오프 2"}
    assert await _names(client, deal_id=seeded) == ["킥오프 2"]
    assert set(await _names(client, action_type="meeting")) == {"킥오프", "킥오프 2"}
    assert set(await _names(client, actor="박영업")) == {"견적 발송", "킥오프 2"}
    assert await _names(client, action_type="meeting", keyword="2") == ["킥오프 2"]
    assert await _names(client, acted_from="2026-03-04T00:00:00+09:00") == []
    assert len(await _names(client, acted_from="2026-03-02T00:00:00+09:00")) == 2


async def test_default_sort_is_latest_activity_first(client: AsyncClient, seeded: str) -> None:
    assert await _names(client) == ["킥오프 2", "견적 발송", "킥오프"]
    assert await _names(client, sort="acted_at_desc") == ["킥오프 2", "견적 발송", "킥오프"]


async def test_keyword_matches_action_next_action_and_memo(
    client: AsyncClient, seeded: str
) -> None:
    assert await _names(client, keyword="견적") == ["견적 발송"]  # action
    assert await _names(client, keyword="계약서") == ["킥오프 2"]  # next_action
    assert await _names(client, keyword="협의") == ["킥오프"]  # memo
    assert await _names(client, keyword="100%") == ["견적 발송"]
    assert await _names(client, keyword="_") == []


async def test_due_range_is_inclusive_on_both_ends(client: AsyncClient, seeded: str) -> None:
    both = await _names(client, due_from="2026-04-01", due_to="2026-04-10")
    assert both == ["킥오프 2", "견적 발송", "킥오프"]
    assert await _names(client, due_from="2026-04-10") == ["킥오프 2", "킥오프"]
    assert await _names(client, due_to="2026-04-01") == ["견적 발송"]
    assert await _names(client, due_from="2026-04-02", due_to="2026-04-09") == []


async def test_sort_by_due_date_breaks_ties_by_latest_activity(
    client: AsyncClient, seeded: str
) -> None:
    assert await _names(client, sort="due_date_asc") == ["견적 발송", "킥오프 2", "킥오프"]
    assert await _names(client, sort="due_date_desc") == ["킥오프 2", "킥오프", "견적 발송"]


async def test_deal_history_endpoint_also_accepts_due_filters_and_sort(
    client: AsyncClient,
) -> None:
    deal_id = await _deal(client)
    await _create(client, deal_id, action="늦음", due_date="2026-05-01")
    await _create(client, deal_id, action="빠름", due_date="2026-04-01")

    response = await client.get(
        f"{DEALS}/{deal_id}/actions", params={"sort": "due_date_asc", "due_to": "2026-04-30"}
    )

    assert response.status_code == 200
    assert [item["action"] for item in response.json()["items"]] == ["빠름"]


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "created_asc"},
        {"sort": "DUE_DATE_ASC"},
        {"due_from": "2026-13-40"},
        {"due_to": "soon"},
        {"due_from": "2026-04-10", "due_to": "2026-04-01"},
        {"limit": 201},
        {"action_type": "dance"},
        {"unknown": "x"},
    ],
)
async def test_invalid_search_params_are_422(client: AsyncClient, params: dict[str, str]) -> None:
    response = await client.get(ACTIONS, params=params)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM)


async def test_inverted_acted_range_is_422(client: AsyncClient) -> None:
    inverted = await client.get(
        ACTIONS,
        params={"acted_from": "2026-03-05T00:00:00+09:00", "acted_to": "2026-03-01T00:00:00+09:00"},
    )

    assert inverted.status_code == 422
    assert inverted.headers["content-type"].startswith(PROBLEM)


async def test_equal_due_bounds_are_allowed(client: AsyncClient, seeded: str) -> None:
    assert await _names(client, due_from="2026-04-01", due_to="2026-04-01") == ["견적 발송"]


async def test_page_limits_are_validated(client: AsyncClient) -> None:
    assert (await client.get(ACTIONS, params={"limit": 201})).status_code == 422
