from typing import TYPE_CHECKING
from uuid import uuid4

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


async def _create(client: AsyncClient, deal_id: str, **overrides: object) -> dict[str, object]:
    response = await client.post(f"{DEALS}/{deal_id}/actions", json=action_payload(**overrides))
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


async def test_create_returns_201_with_location_and_values(client: AsyncClient) -> None:
    deal_id = await _deal(client)

    response = await client.post(f"{DEALS}/{deal_id}/actions", json=action_payload())

    body = response.json()
    assert response.status_code == 201
    assert response.headers["location"] == f"{ACTIONS}/{body['id']}"
    assert body["deal_id"] == deal_id
    assert body["action_type"] == "meeting"
    assert body["title"] == "킥오프 미팅"
    assert body["actor"] == "박영업"
    assert body["acted_at"].startswith("2026-03-02T10:00:00")
    assert body["created_at"].startswith("2026-01-01T09:00:")


async def test_create_for_an_unknown_deal_is_a_404(client: AsyncClient) -> None:
    response = await client.post(f"{DEALS}/{uuid4()}/actions", json=action_payload())

    assert response.status_code == 404
    assert response.json()["type"].endswith("not-found")


async def test_unknown_action_type_is_a_request_validation_error(client: AsyncClient) -> None:
    deal_id = await _deal(client)

    response = await client.post(
        f"{DEALS}/{deal_id}/actions", json=action_payload(action_type="dance")
    )

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_blank_title_and_naive_time_are_422(client: AsyncClient) -> None:
    deal_id = await _deal(client)

    blank = await client.post(f"{DEALS}/{deal_id}/actions", json=action_payload(title=" "))
    naive = await client.post(
        f"{DEALS}/{deal_id}/actions", json=action_payload(acted_at="2026-03-02T10:00:00")
    )

    assert blank.status_code == 422
    assert blank.json()["type"].endswith("invalid-value")
    assert naive.status_code == 422


async def test_get_update_and_delete(client: AsyncClient) -> None:
    created = await _create(client, await _deal(client))

    assert (await client.get(f"{ACTIONS}/{created['id']}")).json() == created
    updated = await client.put(
        f"{ACTIONS}/{created['id']}",
        json=action_payload(action_type="proposal", title="제안 발표"),
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "제안 발표"
    assert updated.json()["deal_id"] == created["deal_id"]
    assert (await client.delete(f"{ACTIONS}/{created['id']}")).status_code == 204
    assert (await client.get(f"{ACTIONS}/{created['id']}")).status_code == 404
    assert (await client.delete(f"{ACTIONS}/{created['id']}")).status_code == 404


async def test_update_cannot_send_a_different_deal(client: AsyncClient) -> None:
    created = await _create(client, await _deal(client))

    response = await client.put(
        f"{ACTIONS}/{created['id']}", json=action_payload(deal_id=str(uuid4()))
    )

    assert response.status_code == 422  # deal_id는 허용되지 않는 필드


async def test_deal_history_lists_latest_first_and_checks_the_deal(client: AsyncClient) -> None:
    deal_id = await _deal(client)
    await _create(client, deal_id, title="먼저", acted_at="2026-03-01T10:00:00+09:00")
    await _create(client, deal_id, title="나중", acted_at="2026-03-05T10:00:00+09:00")

    page = (await client.get(f"{DEALS}/{deal_id}/actions")).json()

    assert [item["title"] for item in page["items"]] == ["나중", "먼저"]
    assert (page["offset"], page["limit"]) == (0, 50)
    assert (await client.get(f"{DEALS}/{uuid4()}/actions")).status_code == 404


async def test_global_search_filters(client: AsyncClient) -> None:
    first, second = await _deal(client), await _deal(client, "DEAL-002")
    await _create(client, first, title="킥오프", action_type="meeting", actor="김영업")
    await _create(client, first, title="견적 발송", action_type="email", actor="박영업")
    await _create(client, second, title="킥오프 2", action_type="meeting", actor="박영업")

    async def titles(**params: str) -> set[str]:
        response = await client.get(ACTIONS, params=params)
        assert response.status_code == 200, response.text
        return {item["title"] for item in response.json()["items"]}

    assert await titles() == {"킥오프", "견적 발송", "킥오프 2"}
    assert await titles(deal_id=second) == {"킥오프 2"}
    assert await titles(action_type="meeting") == {"킥오프", "킥오프 2"}
    assert await titles(actor="박영업") == {"견적 발송", "킥오프 2"}
    assert await titles(keyword="견적") == {"견적 발송"}
    assert await titles(action_type="meeting", keyword="2") == {"킥오프 2"}
    assert await titles(acted_from="2026-03-03T00:00:00+09:00") == set()
    assert await titles(acted_from="2026-03-02T00:00:00+09:00") == {
        "킥오프",
        "견적 발송",
        "킥오프 2",
    }


async def test_search_validation(client: AsyncClient) -> None:
    assert (await client.get(ACTIONS, params={"limit": 201})).status_code == 422
    assert (await client.get(ACTIONS, params={"action_type": "dance"})).status_code == 422
    assert (await client.get(ACTIONS, params={"unknown": "x"})).status_code == 422
    inverted = await client.get(
        ACTIONS,
        params={"acted_from": "2026-03-05T00:00:00+09:00", "acted_to": "2026-03-01T00:00:00+09:00"},
    )
    assert inverted.status_code == 422
    assert inverted.headers["content-type"].startswith(PROBLEM)


async def test_history_survives_deleting_the_deal(client: AsyncClient) -> None:
    deal_id = await _deal(client)
    await _create(client, deal_id)
    await client.delete(f"{DEALS}/{deal_id}")

    page = (await client.get(f"{DEALS}/{deal_id}/actions")).json()

    assert len(page["items"]) == 1
    assert (
        await client.post(f"{DEALS}/{deal_id}/actions", json=action_payload())
    ).status_code == 404
