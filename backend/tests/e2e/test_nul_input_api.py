"""NUL 문자 입력은 500이 아니라 422 invalid-value다(검색 조건과 등록 본문).

Action의 NUL 검증(등록 본문·검색어)은 functional/actions가 다룬다.
"""

from typing import TYPE_CHECKING

from tests.e2e.payloads import deal_payload

if TYPE_CHECKING:
    from httpx import AsyncClient, Response

NUL = "a\x00b"
DB_ERROR_TOKENS = ("asyncpg", "dbapierror", "sqlalchemy", "postgres", "0x00")


def _assert_invalid_value(response: Response) -> None:
    body = response.json()
    assert response.status_code == 422, body
    assert body["type"].endswith("invalid-value"), body
    detail = str(body.get("detail", "")).lower()
    assert not any(token in detail for token in DB_ERROR_TOKENS), detail


async def test_deal_search_keyword_with_nul_is_422_invalid_value(client: AsyncClient) -> None:
    _assert_invalid_value(await client.get("/api/v1/deals", params={"keyword": NUL}))


async def test_deal_search_text_condition_with_nul_is_422(client: AsyncClient) -> None:
    _assert_invalid_value(await client.get("/api/v1/deals", params={"vendor": NUL}))


async def test_deal_owner_filter_with_nul_is_a_request_validation_error(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/deals", params={"owner_user_id": NUL})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_deal_registration_with_nul_is_422(client: AsyncClient) -> None:
    response = await client.post("/api/v1/deals", json=deal_payload(name=NUL))

    _assert_invalid_value(response)
