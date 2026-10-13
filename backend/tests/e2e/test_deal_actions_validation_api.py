"""Deal 이력(활동) 입력 검증: 필수 필드, 길이 경계, NUL, due_date 형식, 구 필드 거부(AC2~4)."""

from typing import TYPE_CHECKING

import pytest

from tests.e2e.payloads import action_payload, customer_payload, deal_payload

if TYPE_CHECKING:
    from httpx import AsyncClient

DEALS = "/api/v1/deals"


@pytest.fixture
async def url(client: AsyncClient) -> str:
    customer = (await client.post("/api/v1/customers", json=customer_payload())).json()
    deal = (await client.post(DEALS, json=deal_payload(customer["id"]))).json()
    return f"{DEALS}/{deal['id']}/actions"


def _without(field: str) -> dict[str, object]:
    payload = action_payload()
    del payload[field]
    return payload


@pytest.mark.parametrize("field", ["action", "next_action", "due_date"])
async def test_missing_required_field_is_422_request_validation(
    client: AsyncClient, url: str, field: str
) -> None:
    response = await client.post(url, json=_without(field))

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


@pytest.mark.parametrize("field", ["action", "next_action", "due_date"])
async def test_null_required_field_is_422_request_validation(
    client: AsyncClient, url: str, field: str
) -> None:
    response = await client.post(url, json=action_payload(**{field: None}))

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


@pytest.mark.parametrize("field", ["action", "next_action"])
async def test_blank_text_is_422_invalid_value(client: AsyncClient, url: str, field: str) -> None:
    response = await client.post(url, json=action_payload(**{field: "   "}))

    assert response.status_code == 422
    assert response.json()["type"].endswith("invalid-value")


async def test_naive_acted_at_is_422(client: AsyncClient, url: str) -> None:
    response = await client.post(url, json=action_payload(acted_at="2026-03-02T10:00:00"))

    assert response.status_code == 422


async def test_unknown_action_type_is_a_request_validation_error(
    client: AsyncClient, url: str
) -> None:
    response = await client.post(url, json=action_payload(action_type="dance"))

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


@pytest.mark.parametrize("legacy", ["title", "content"])
async def test_legacy_title_and_content_fields_are_rejected(
    client: AsyncClient, url: str, legacy: str
) -> None:
    response = await client.post(url, json=action_payload(**{legacy: "구 필드"}))

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_legacy_only_payload_is_rejected_as_missing_action(
    client: AsyncClient, url: str
) -> None:
    payload = _without("action")
    payload["title"] = "킥오프"

    assert (await client.post(url, json=payload)).status_code == 422


@pytest.mark.parametrize(
    ("field", "limit"), [("action", 200), ("next_action", 200), ("memo", 4000)]
)
async def test_text_length_limits(client: AsyncClient, url: str, field: str, limit: int) -> None:
    exact = await client.post(url, json=action_payload(**{field: "가" * limit}))
    over = await client.post(url, json=action_payload(**{field: "가" * (limit + 1)}))

    assert exact.status_code == 201
    assert over.status_code == 422


@pytest.mark.parametrize("field", ["action", "next_action", "memo", "actor"])
async def test_nul_character_is_422(client: AsyncClient, url: str, field: str) -> None:
    response = await client.post(url, json=action_payload(**{field: "가\u0000나"}))

    assert response.status_code == 422


@pytest.mark.parametrize("value", ["2026-13-40", "내일", "2026-03-10T10:30:00+09:00", "20260310x"])
async def test_due_date_must_be_a_calendar_date(client: AsyncClient, url: str, value: str) -> None:
    response = await client.post(url, json=action_payload(due_date=value))

    assert response.status_code == 422


async def test_due_date_may_be_in_the_past_and_before_acted_at(
    client: AsyncClient, url: str
) -> None:
    response = await client.post(
        url, json=action_payload(due_date="2020-01-01", acted_at="2026-03-02T10:00:00+09:00")
    )

    assert response.status_code == 201
    assert response.json()["due_date"] == "2020-01-01"
