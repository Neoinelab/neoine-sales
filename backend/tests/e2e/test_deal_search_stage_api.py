"""GET /api/v1/deals?stage=... 단계 검색 조건(Fake UoW). 다른 조건과 AND로 결합한다."""

from typing import TYPE_CHECKING

from tests.e2e.payloads import customer_payload, deal_payload

if TYPE_CHECKING:
    from httpx import AsyncClient

DEALS = "/api/v1/deals"


async def _customer_id(client: AsyncClient) -> str:
    response = await client.post("/api/v1/customers", json=customer_payload())
    return str(response.json()["id"])


async def _create(client: AsyncClient, customer_id: str, code: str, **overrides: object) -> None:
    response = await client.post(DEALS, json=deal_payload(customer_id, code=code, **overrides))
    assert response.status_code == 201, response.text


async def _codes(client: AsyncClient, **params: object) -> list[str]:
    response = await client.get(DEALS, params=params)  # type: ignore[arg-type]
    assert response.status_code == 200, response.text
    return [item["code"] for item in response.json()["items"]]


async def _move(client: AsyncClient, deal_id: str, stage: str) -> None:
    response = await client.post(f"{DEALS}/{deal_id}/stage", json={"stage": stage, "reason": "x"})
    assert response.status_code == 200, response.text


async def _create_id(client: AsyncClient, customer_id: str, code: str, **overrides: object) -> str:
    response = await client.post(DEALS, json=deal_payload(customer_id, code=code, **overrides))
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def test_search_by_stage(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, "D-1")
    lost = await _create_id(client, customer_id, "D-2")
    won = await _create_id(client, customer_id, "D-3")
    await _move(client, lost, "lost")
    await _move(client, won, "contract_completed")

    assert await _codes(client, stage="lost") == ["D-2"]
    assert await _codes(client, stage="prospecting") == ["D-1"]
    assert await _codes(client, stage="contract_completed") == ["D-3"]
    assert await _codes(client, stage="introduction") == []
    assert await _codes(client) == ["D-1", "D-2", "D-3"]


async def test_search_stage_combines_with_other_conditions_and_paging(
    client: AsyncClient, owners: dict[str, str]
) -> None:
    customer_id = await _customer_id(client)
    x, park = owners["x"], owners["park"]
    ids = [
        await _create_id(client, customer_id, "D-1", owner_user_id=x),
        await _create_id(client, customer_id, "D-2", owner_user_id=park),
        await _create_id(client, customer_id, "D-3", owner_user_id=park),
        await _create_id(client, customer_id, "D-4", owner_user_id=park),
    ]
    for deal_id in ids[:3]:
        await _move(client, deal_id, "lost")

    assert await _codes(client, stage="lost", owner_user_id=park) == ["D-2", "D-3"]
    assert await _codes(client, stage="lost", owner_user_id=park, offset=1, limit=1) == ["D-3"]
    assert await _codes(client, stage="lost", keyword="d-4") == []


async def test_search_by_stage_excludes_deleted_deals(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    gone = await _create_id(client, customer_id, "D-1")
    assert (await client.delete(f"{DEALS}/{gone}")).status_code == 204  # 이력이 없어 물리 삭제

    assert await _codes(client, stage="prospecting") == []
    assert await _codes(client) == []


async def test_search_rejects_unknown_stage(client: AsyncClient) -> None:
    for value in ("won", "LOST"):
        response = await client.get(DEALS, params={"stage": value})

        assert response.status_code == 422, value
        assert response.json()["type"].endswith("request-validation")


async def test_list_response_items_include_the_stage_field(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, "D-1")

    items = (await client.get(DEALS)).json()["items"]

    assert items[0]["stage"] == "prospecting"
