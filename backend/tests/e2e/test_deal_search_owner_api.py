"""GET /api/v1/deals 담당자 검색: owner_user_id 필터, 퇴사한 담당자, 키워드(담당자 이름)(AC10)."""

from typing import TYPE_CHECKING

import pytest

from tests.e2e.payloads import customer_payload, deal_payload

if TYPE_CHECKING:
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

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


async def test_search_by_owner_user_id_finds_a_resigned_owners_deals(
    client: AsyncClient, use_cases: FakeUseCases, owners: dict[str, str]
) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, "D-1", owner_user_id=owners["y"])
    await use_cases.resign_user(await use_cases.user_id_of("y"))

    assert await _codes(client, owner_user_id=owners["y"]) == ["D-1"]


async def test_keyword_matches_the_owners_name_through_the_users_table(
    client: AsyncClient, owners: dict[str, str]
) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, "D-1", owner_user_id=owners["park"])
    await _create(client, customer_id, "D-2", owner_user_id=owners["x"])

    assert await _codes(client, keyword="PARK") == ["D-1"]


@pytest.mark.parametrize("value", ["박영업", "not-a-uuid", ""])
async def test_search_rejects_a_malformed_owner_user_id_as_request_validation(
    client: AsyncClient, value: str
) -> None:
    response = await client.get(DEALS, params={"owner_user_id": value})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_the_free_text_owner_parameter_no_longer_exists(client: AsyncClient) -> None:
    response = await client.get(DEALS, params={"owner": "박영업"})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")
