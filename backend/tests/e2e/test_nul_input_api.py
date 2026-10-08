"""NUL 문자 입력은 500이 아니라 422 invalid-value다(검색 조건과 등록 본문)."""

from typing import TYPE_CHECKING

import pytest

from tests.e2e.payloads import customer_payload, deal_payload, partner_payload

if TYPE_CHECKING:
    from httpx import AsyncClient, Response

NUL = "a\x00b"
PATHS = ["/api/v1/customers", "/api/v1/partners", "/api/v1/deals", "/api/v1/deal-actions"]
DB_ERROR_TOKENS = ("asyncpg", "dbapierror", "sqlalchemy", "postgres", "0x00")


def _assert_invalid_value(response: Response) -> None:
    body = response.json()
    assert response.status_code == 422, body
    assert body["type"].endswith("invalid-value"), body
    detail = str(body.get("detail", "")).lower()
    assert not any(token in detail for token in DB_ERROR_TOKENS), detail


@pytest.mark.parametrize("path", PATHS)
async def test_search_keyword_with_nul_is_422_invalid_value(client: AsyncClient, path: str) -> None:
    _assert_invalid_value(await client.get(path, params={"keyword": NUL}))


@pytest.mark.parametrize("param", ["owner", "vendor"])
async def test_deal_search_text_condition_with_nul_is_422(client: AsyncClient, param: str) -> None:
    _assert_invalid_value(await client.get("/api/v1/deals", params={param: NUL}))


async def test_deal_action_actor_with_nul_is_422(client: AsyncClient) -> None:
    _assert_invalid_value(await client.get("/api/v1/deal-actions", params={"actor": NUL}))


async def test_customer_registration_with_nul_is_422(client: AsyncClient) -> None:
    response = await client.post("/api/v1/customers", json=customer_payload(company_name=NUL))

    _assert_invalid_value(response)


async def test_partner_registration_with_nul_is_422(client: AsyncClient) -> None:
    response = await client.post("/api/v1/partners", json=partner_payload(company_name=NUL))

    _assert_invalid_value(response)


async def test_deal_registration_with_nul_is_422(client: AsyncClient) -> None:
    customer = (await client.post("/api/v1/customers", json=customer_payload())).json()

    response = await client.post("/api/v1/deals", json=deal_payload(customer["id"], name=NUL))

    _assert_invalid_value(response)
