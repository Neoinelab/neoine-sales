"""GET /api/v1/deals/pipeline: 8개 단계, 건수, 통화별 문자열 합계."""

from typing import TYPE_CHECKING
from uuid import uuid4

from tests.e2e.payloads import customer_payload, deal_payload

if TYPE_CHECKING:
    from httpx import AsyncClient

DEALS = "/api/v1/deals"
PIPELINE = f"{DEALS}/pipeline"
STAGES = [
    "prospecting",
    "introduction",
    "poc_preparation",
    "poc_completed",
    "technical_evaluation",
    "price_negotiation",
    "contract_completed",
    "lost",
]


async def _customer_id(client: AsyncClient) -> str:
    return str((await client.post("/api/v1/customers", json=customer_payload())).json()["id"])


async def _deal(client: AsyncClient, customer_id: str, code: str, **overrides: object) -> str:
    response = await client.post(DEALS, json=deal_payload(customer_id, code=code, **overrides))
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _move(client: AsyncClient, deal_id: str, stage: str) -> None:
    response = await client.post(f"{DEALS}/{deal_id}/stage", json={"stage": stage, "reason": "x"})
    assert response.status_code == 200, response.text


async def test_empty_pipeline_lists_all_eight_stages_with_zero(client: AsyncClient) -> None:
    response = await client.get(PIPELINE)

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"stages"}
    assert [s["stage"] for s in body["stages"]] == STAGES
    assert all(s["deal_count"] == 0 and s["totals"] == [] for s in body["stages"])


async def test_pipeline_returns_eight_stages_with_counts_and_string_totals(
    client: AsyncClient,
) -> None:
    customer_id = await _customer_id(client)
    await _deal(client, customer_id, "D-1")
    await _deal(client, customer_id, "D-2", revenue_amount="50.5")
    usd = await _deal(client, customer_id, "D-3", revenue_amount="5.5", revenue_currency="USD")
    await _move(client, usd, "price_negotiation")

    body = (await client.get(PIPELINE)).json()

    by_stage = {s["stage"]: s for s in body["stages"]}
    assert [s["stage"] for s in body["stages"]] == STAGES
    assert by_stage["prospecting"]["deal_count"] == 2
    assert by_stage["prospecting"]["totals"] == [{"currency": "KRW", "amount": "150000050.5"}]
    assert by_stage["price_negotiation"]["deal_count"] == 1
    assert by_stage["price_negotiation"]["totals"] == [{"currency": "USD", "amount": "5.5"}]
    assert by_stage["lost"]["totals"] == []


async def test_pipeline_totals_are_sorted_by_currency_code(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    await _deal(client, customer_id, "D-1", revenue_amount="1", revenue_currency="USD")
    await _deal(client, customer_id, "D-2", revenue_amount="2", revenue_currency="KRW")
    await _deal(client, customer_id, "D-3", revenue_amount="3", revenue_currency="EUR")

    first = (await client.get(PIPELINE)).json()["stages"][0]

    assert [t["currency"] for t in first["totals"]] == ["EUR", "KRW", "USD"]
    assert first["deal_count"] == 3


async def test_pipeline_excludes_deleted_deals_and_follows_moves(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    kept = await _deal(client, customer_id, "D-1")
    gone = await _deal(client, customer_id, "D-2")
    await client.delete(f"{DEALS}/{gone}")
    await _move(client, kept, "lost")

    stages = {s["stage"]: s for s in (await client.get(PIPELINE)).json()["stages"]}

    assert stages["prospecting"]["deal_count"] == 0
    assert stages["lost"]["deal_count"] == 1


async def test_pipeline_is_not_confused_with_a_deal_id(client: AsyncClient) -> None:
    assert (await client.get(PIPELINE)).status_code == 200
    assert (await client.get(f"{DEALS}/{uuid4()}")).status_code == 404


async def test_pipeline_rejects_unknown_query_parameter(client: AsyncClient) -> None:
    response = await client.get(PIPELINE, params={"x": "1"})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_pipeline_requires_login(anonymous_client: AsyncClient) -> None:
    response = await anonymous_client.get(PIPELINE)

    assert response.status_code == 401
    assert response.json()["type"].endswith("unauthenticated")
