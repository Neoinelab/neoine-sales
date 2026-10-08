"""POST /deals/{id}/stage, GET /deals/{id}/stage-changes 계약(Fake UoW)."""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from tests.e2e.payloads import customer_payload, deal_payload

if TYPE_CHECKING:
    from httpx import AsyncClient, Response

DEALS = "/api/v1/deals"
PROBLEM = "application/problem+json"
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


async def _deal(client: AsyncClient, **overrides: object) -> dict[str, object]:
    customer = await client.post("/api/v1/customers", json=customer_payload())
    response = await client.post(DEALS, json=deal_payload(str(customer.json()["id"]), **overrides))
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


async def _change(client: AsyncClient, deal_id: object, stage: str, **extra: object) -> Response:
    return await client.post(f"{DEALS}/{deal_id}/stage", json={"stage": stage, **extra})


async def _history(client: AsyncClient, deal_id: object, **params: object) -> dict[str, Any]:
    response = await client.get(f"{DEALS}/{deal_id}/stage-changes", params=params)  # type: ignore[arg-type]
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


async def test_created_deal_starts_at_prospecting(client: AsyncClient) -> None:
    deal = await _deal(client)

    assert deal["stage"] == "prospecting"
    assert (await client.get(f"{DEALS}/{deal['id']}")).json()["stage"] == "prospecting"
    assert (await client.get(f"{DEALS}/by-code/deal-001")).json()["stage"] == "prospecting"
    assert (await client.get(DEALS)).json()["items"][0]["stage"] == "prospecting"


async def test_change_stage_returns_the_updated_deal(client: AsyncClient) -> None:
    deal = await _deal(client)

    response = await _change(client, deal["id"], "price_negotiation")

    body = response.json()
    assert response.status_code == 200
    assert body["stage"] == "price_negotiation"
    assert body["id"] == deal["id"]
    assert body["code"] == deal["code"]
    assert body["updated_at"] != deal["updated_at"]
    assert (await client.get(f"{DEALS}/{deal['id']}")).json()["stage"] == "price_negotiation"


@pytest.mark.parametrize(
    ("start", "target"), [("contract_completed", "prospecting"), ("lost", "introduction")]
)
async def test_stage_moves_freely_backward_and_out_of_lost(
    client: AsyncClient, start: str, target: str
) -> None:
    deal = await _deal(client)
    first = await _change(client, deal["id"], start, reason="사유")
    assert first.status_code == 200

    response = await _change(client, deal["id"], target)

    assert response.status_code == 200
    assert response.json()["stage"] == target


@pytest.mark.parametrize("stage", STAGES[1:])
async def test_every_stage_can_be_reached(client: AsyncClient, stage: str) -> None:
    deal = await _deal(client)

    response = await _change(client, deal["id"], stage, reason="사유")

    assert response.status_code == 200
    assert response.json()["stage"] == stage


async def test_lost_without_reason_is_422_and_nothing_changes(client: AsyncClient) -> None:
    deal = await _deal(client)

    for extra in ({}, {"reason": None}, {"reason": ""}, {"reason": "   "}):
        response = await _change(client, deal["id"], "lost", **extra)

        assert response.status_code == 422, extra
        assert response.headers["content-type"].startswith(PROBLEM)
        assert response.json()["type"].endswith("invalid-value")
    assert (await client.get(f"{DEALS}/{deal['id']}")).json()["stage"] == "prospecting"
    assert (await _history(client, deal["id"]))["items"] == []


async def test_lost_with_reason_is_recorded_trimmed(client: AsyncClient) -> None:
    deal = await _deal(client)

    response = await _change(client, deal["id"], "lost", reason="  경쟁사 선정  ")

    assert response.status_code == 200
    assert (await _history(client, deal["id"]))["items"][0]["reason"] == "경쟁사 선정"


async def test_reason_over_500_chars_is_422_and_exactly_500_is_accepted(
    client: AsyncClient,
) -> None:
    deal = await _deal(client)

    too_long = await _change(client, deal["id"], "lost", reason="가" * 501)
    exact = await _change(client, deal["id"], "lost", reason="가" * 500)

    assert too_long.status_code == 422
    assert too_long.json()["type"].endswith("invalid-value")
    assert exact.status_code == 200


async def test_reason_is_an_optional_memo_for_other_stages(client: AsyncClient) -> None:
    deal = await _deal(client)

    await _change(client, deal["id"], "introduction", reason="  자료 전달 ")
    await _change(client, deal["id"], "poc_preparation", reason="   ")
    await _change(client, deal["id"], "poc_completed")

    items = (await _history(client, deal["id"]))["items"]
    assert [i["reason"] for i in items] == [None, None, "자료 전달"]  # 최신순


async def test_same_stage_is_409_and_records_nothing(client: AsyncClient) -> None:
    deal = await _deal(client)

    response = await _change(client, deal["id"], "prospecting")

    assert response.status_code == 409
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json()["type"].endswith("invalid-state")
    assert (await _history(client, deal["id"]))["items"] == []


@pytest.mark.parametrize("stage", ["prospecting", "lost"])
async def test_same_stage_409_detail_does_not_expose_the_stage_code(
    client: AsyncClient, stage: str
) -> None:
    deal = await _deal(client)
    if stage != "prospecting":
        await _change(client, deal["id"], stage, reason="예산 부족")

    response = await _change(client, deal["id"], stage, reason="예산 부족")

    assert response.status_code == 409
    assert stage not in response.json()["detail"], "화면에 영문 단계 코드가 노출된다"


@pytest.mark.parametrize(
    "body",
    [
        {"stage": "won"},
        {"stage": "Lost"},
        {"stage": ""},
        {},
        {"stage": "lost", "reason": 123},
        {"stage": "introduction", "owner": "x"},
    ],
)
async def test_stage_change_validation(client: AsyncClient, body: dict[str, object]) -> None:
    deal = await _deal(client)

    response = await client.post(f"{DEALS}/{deal['id']}/stage", json=body)

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")
    assert (await _history(client, deal["id"]))["items"] == []


async def test_stage_change_with_invalid_deal_id_is_422(client: AsyncClient) -> None:
    response = await client.post(f"{DEALS}/not-a-uuid/stage", json={"stage": "introduction"})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_unknown_or_deleted_deal_is_404(client: AsyncClient) -> None:
    deal = await _deal(client)
    await client.delete(f"{DEALS}/{deal['id']}")

    for deal_id in (uuid4(), deal["id"]):
        response = await _change(client, deal_id, "introduction")

        assert response.status_code == 404
        assert response.json()["type"].endswith("not-found")


async def test_put_keeps_stage_and_rejects_stage_in_body(client: AsyncClient) -> None:
    deal = await _deal(client)
    await _change(client, deal["id"], "lost", reason="예산")
    payload = deal_payload(str(deal["customer_id"]), name="이름 변경")

    kept = await client.put(f"{DEALS}/{deal['id']}", json=payload)
    rejected = await client.put(f"{DEALS}/{deal['id']}", json={**payload, "stage": "prospecting"})

    assert kept.status_code == 200
    assert kept.json()["stage"] == "lost"
    assert kept.json()["name"] == "이름 변경"
    assert rejected.status_code == 422
    assert rejected.json()["type"].endswith("request-validation")
    assert (await client.get(f"{DEALS}/{deal['id']}")).json()["stage"] == "lost"


async def test_post_deal_with_stage_in_body_is_rejected(client: AsyncClient) -> None:
    customer = await client.post("/api/v1/customers", json=customer_payload())

    response = await client.post(
        DEALS, json={**deal_payload(str(customer.json()["id"])), "stage": "lost"}
    )

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_put_on_a_lost_deal_is_allowed(client: AsyncClient) -> None:
    deal = await _deal(client)
    await _change(client, deal["id"], "lost", reason="예산")

    response = await client.put(
        f"{DEALS}/{deal['id']}", json=deal_payload(str(deal["customer_id"]), owner="최영업")
    )

    assert response.status_code == 200
    assert response.json()["owner"] == "최영업"


async def test_stage_change_and_history_require_login_and_csrf(
    anonymous_client: AsyncClient,
) -> None:
    deal_id = uuid4()

    assert (
        await anonymous_client.post(f"{DEALS}/{deal_id}/stage", json={"stage": "lost"})
    ).status_code == 401
    assert (await anonymous_client.get(f"{DEALS}/{deal_id}/stage-changes")).status_code == 401
