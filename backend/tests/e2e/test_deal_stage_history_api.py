"""GET /deals/{id}/stage-changes: 최신순 이력, 페이지, 삭제된 딜의 이력, 오류(Fake UoW)."""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from tests.e2e.conftest import DEFAULT_LOGIN, DEFAULT_NAME
from tests.e2e.payloads import customer_payload, deal_payload

if TYPE_CHECKING:
    from httpx import AsyncClient

DEALS = "/api/v1/deals"


async def _deal(client: AsyncClient, **overrides: object) -> dict[str, object]:
    customer = await client.post("/api/v1/customers", json=customer_payload())
    response = await client.post(DEALS, json=deal_payload(str(customer.json()["id"]), **overrides))
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


async def _change(client: AsyncClient, deal_id: object, stage: str, **extra: object) -> None:
    response = await client.post(f"{DEALS}/{deal_id}/stage", json={"stage": stage, **extra})
    assert response.status_code == 200, response.text


async def _history(client: AsyncClient, deal_id: object, **params: object) -> dict[str, Any]:
    response = await client.get(f"{DEALS}/{deal_id}/stage-changes", params=params)  # type: ignore[arg-type]
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


async def test_history_lists_latest_first_with_changer(client: AsyncClient) -> None:
    deal = await _deal(client)
    await _change(client, deal["id"], "introduction")
    await _change(client, deal["id"], "lost", reason="예산 삭감")

    body = await _history(client, deal["id"])

    items = body["items"]
    assert (body["offset"], body["limit"]) == (0, 50)
    assert set(body) == {"items", "offset", "limit"}
    assert [(i["from_stage"], i["to_stage"]) for i in items] == [
        ("introduction", "lost"),
        ("prospecting", "introduction"),
    ]
    latest = items[0]
    assert set(latest) == {
        "id", "deal_id", "from_stage", "to_stage", "reason",
        "changed_by_subject", "changed_by_name", "changed_at",
    }  # fmt: skip
    assert latest["deal_id"] == deal["id"]
    assert latest["reason"] == "예산 삭감"
    assert latest["changed_by_subject"] == DEFAULT_LOGIN
    assert latest["changed_by_name"] == DEFAULT_NAME
    assert latest["changed_at"] > items[1]["changed_at"]


async def test_history_pages_with_offset_and_limit(client: AsyncClient) -> None:
    deal = await _deal(client)
    for stage in ("introduction", "poc_preparation", "poc_completed"):
        await _change(client, deal["id"], stage)

    body = await _history(client, deal["id"], offset=1, limit=1)

    assert [i["to_stage"] for i in body["items"]] == ["poc_preparation"]
    assert (body["offset"], body["limit"]) == (1, 1)


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}, {"x": "1"}])
async def test_history_rejects_invalid_query(
    client: AsyncClient, params: dict[str, object]
) -> None:
    deal = await _deal(client)

    response = await client.get(f"{DEALS}/{deal['id']}/stage-changes", params=params)  # type: ignore[arg-type]

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_history_of_a_deleted_deal_is_still_readable(client: AsyncClient) -> None:
    deal = await _deal(client)
    await _change(client, deal["id"], "introduction")
    await client.delete(f"{DEALS}/{deal['id']}")

    assert len((await _history(client, deal["id"]))["items"]) == 1


async def test_history_of_an_unknown_deal_is_404(client: AsyncClient) -> None:
    response = await client.get(f"{DEALS}/{uuid4()}/stage-changes")

    assert response.status_code == 404
    assert response.json()["type"].endswith("not-found")


async def test_history_only_contains_the_requested_deal(client: AsyncClient) -> None:
    first = await _deal(client)
    second = await _deal(client, code="deal-002")
    await _change(client, first["id"], "introduction")

    assert (await _history(client, second["id"]))["items"] == []
