"""GET /api/v1/partners 검색(키워드) 계약(Fake UoW): C-2, C-4, 인증."""

from typing import TYPE_CHECKING

import pytest

from tests.e2e.payloads import partner_payload

if TYPE_CHECKING:
    from httpx import AsyncClient

BASE = "/api/v1/partners"


async def _create(client: AsyncClient, **overrides: object) -> None:
    response = await client.post(BASE, json=partner_payload(**overrides))
    assert response.status_code == 201, response.text


async def _names(client: AsyncClient, **params: object) -> list[str]:
    response = await client.get(BASE, params=params)  # type: ignore[arg-type]
    assert response.status_code == 200, response.text
    return [item["company_name"] for item in response.json()["items"]]


async def test_search_by_keyword_returns_matching_partners(client: AsyncClient) -> None:
    await _create(client, company_name="Alpha 상사")
    await _create(client, company_name="베타")
    await _create(client, company_name="무관", contact_name="알파 담당")
    await _create(client, company_name="감마", contact_title="ALPHA 팀장")

    assert await _names(client, keyword="alpha") == ["Alpha 상사", "감마"]
    assert await _names(client, keyword="알파") == ["무관"]


async def test_search_by_email_ignores_case(client: AsyncClient) -> None:
    await _create(client, company_name="메일", email="Search.Me@Sample.Example")
    await _create(client, company_name="다른", email="other@sample.example")

    assert await _names(client, keyword="SEARCH.ME@") == ["메일"]


async def test_search_by_phone_matches_stored_text(client: AsyncClient) -> None:
    await _create(client, company_name="전화", phone="031-777-4321")
    await _create(client, company_name="다른전화", phone="02-555-1111")

    assert await _names(client, keyword="777-43") == ["전화"]
    assert await _names(client, keyword="031777") == []


async def test_search_treats_percent_literally(client: AsyncClient) -> None:
    await _create(client, company_name="백프로", contact_title="100% 책임")
    await _create(client, company_name="천", contact_title="1000 책임")

    assert await _names(client, keyword="100%") == ["백프로"]


async def test_search_excludes_deleted_partners(client: AsyncClient) -> None:
    await _create(client, company_name="Zed 유지")
    await _create(client, company_name="무관")
    gone = (await client.post(BASE, json=partner_payload(company_name="Zed 삭제"))).json()
    await client.delete(f"{BASE}/{gone['id']}")

    assert await _names(client, keyword="zed") == ["Zed 유지"]


async def test_search_keeps_creation_order_and_pages_after_filtering(client: AsyncClient) -> None:
    for n in range(4):
        await _create(client, company_name=f"Hit{n}")
        await _create(client, company_name=f"other{n}")

    assert await _names(client, keyword="hit", offset=1, limit=2) == ["Hit1", "Hit2"]


async def test_search_blank_keyword_is_no_condition(client: AsyncClient) -> None:
    await _create(client, company_name="가")
    await _create(client, company_name="나")

    assert await _names(client, keyword="   ") == ["가", "나"]


async def test_search_conditions_keep_page_shape(client: AsyncClient) -> None:
    await _create(client, company_name="가")

    body = (await client.get(BASE, params={"keyword": "가", "limit": 10})).json()

    assert set(body) == {"items", "offset", "limit"}
    assert (body["offset"], body["limit"]) == (0, 10)


async def test_search_accepts_keyword_of_100_chars(client: AsyncClient) -> None:
    response = await client.get(BASE, params={"keyword": "k" * 100})

    assert response.status_code == 200


async def test_search_rejects_keyword_over_100_chars(client: AsyncClient) -> None:
    response = await client.get(BASE, params={"keyword": "k" * 101})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


@pytest.mark.parametrize("params", [{"foo": "1"}, {"keyword": "a", "company_name": "a"}])
async def test_search_rejects_unknown_query_parameter(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get(BASE, params=params)

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


@pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"limit": 201}])
async def test_search_keeps_paging_rules_with_keyword(
    client: AsyncClient, params: dict[str, int]
) -> None:
    response = await client.get(BASE, params={"keyword": "a", **params})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_search_requires_login(anonymous_client: AsyncClient) -> None:
    response = await anonymous_client.get(BASE, params={"keyword": "a"})

    assert response.status_code == 401
