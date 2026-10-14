"""GET /api/v1/deals 검색·필터·페이지 계약(Fake UoW). 조건 없는 호출은 기존 동작과 같아야 한다."""

from typing import TYPE_CHECKING
from uuid import uuid4

from tests.e2e.payloads import customer_payload, deal_payload, partner_payload

if TYPE_CHECKING:
    from httpx import AsyncClient


DEALS = "/api/v1/deals"


async def _customer_id(client: AsyncClient, name: str = "네오인") -> str:
    response = await client.post("/api/v1/customers", json=customer_payload(company_name=name))
    return str(response.json()["id"])


async def _partner_id(client: AsyncClient) -> str:
    response = await client.post("/api/v1/partners", json=partner_payload())
    return str(response.json()["id"])


async def _create(client: AsyncClient, customer_id: str, code: str, **overrides: object) -> None:
    response = await client.post(DEALS, json=deal_payload(customer_id, code=code, **overrides))
    assert response.status_code == 201, response.text


async def _codes(client: AsyncClient, **params: object) -> list[str]:
    response = await client.get(DEALS, params=params)  # type: ignore[arg-type]
    assert response.status_code == 200, response.text
    return [item["code"] for item in response.json()["items"]]


async def test_list_without_params_keeps_creation_order_and_page_shape(
    client: AsyncClient,
) -> None:
    customer_id = await _customer_id(client)
    for code in ("D-1", "D-2", "D-3"):
        await _create(client, customer_id, code)

    response = await client.get(DEALS)

    body = response.json()
    assert response.status_code == 200
    assert [i["code"] for i in body["items"]] == ["D-1", "D-2", "D-3"]
    assert (body["offset"], body["limit"]) == (0, 50)
    assert set(body) == {"items", "offset", "limit"}
    assert {
        "id", "code", "name", "owner", "vendor", "solution", "revenue_amount",
        "revenue_currency", "revenue_date", "customer_id", "partner_id",
        "created_at", "updated_at",
    } <= set(body["items"][0])  # fmt: skip
    assert set(body["items"][0]["owner"]) == {"id", "name", "resigned", "label"}


async def test_list_excludes_deleted_deals_even_when_they_match(
    client: AsyncClient, owners: dict[str, str]
) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, "KEEP", owner_user_id=owners["x"])
    gone = await client.post(
        DEALS, json=deal_payload(customer_id, code="GONE", owner_user_id=owners["x"])
    )
    await client.delete(f"{DEALS}/{gone.json()['id']}")

    assert await _codes(client, owner_user_id=owners["x"]) == ["KEEP"]
    assert await _codes(client) == ["KEEP"]


async def test_list_with_offset_and_limit_only_returns_same_slice(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    for code in ("D-1", "D-2", "D-3"):
        await _create(client, customer_id, code)

    response = await client.get(DEALS, params={"offset": 1, "limit": 1})

    body = response.json()
    assert [i["code"] for i in body["items"]] == ["D-2"]
    assert (body["offset"], body["limit"]) == (1, 1)


async def test_list_rejects_limit_over_max(client: AsyncClient) -> None:
    response = await client.get(DEALS, params={"limit": 201})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_list_rejects_limit_below_min(client: AsyncClient) -> None:
    response = await client.get(DEALS, params={"limit": 0})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_list_rejects_negative_offset(client: AsyncClient) -> None:
    response = await client.get(DEALS, params={"offset": -1})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_list_accepts_limit_max(client: AsyncClient) -> None:
    response = await client.get(DEALS, params={"limit": 200})

    assert response.status_code == 200
    assert response.json()["limit"] == 200


async def test_search_by_keyword_returns_matching_deals(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, "D-1", name="ERP 구축")
    await _create(client, customer_id, "D-2", name="CRM 도입")
    await _create(client, customer_id, "D-3", name="보안", solution="erp 연동")

    assert await _codes(client, keyword="erp") == ["D-1", "D-3"]


async def test_search_by_keyword_finds_code_ignoring_case(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, "ALPHA-1", name="가")
    await _create(client, customer_id, "BETA-1", name="나")

    assert await _codes(client, keyword="alpha") == ["ALPHA-1"]


async def test_search_by_keyword_treats_percent_literally(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, "D-1", name="100% 달성")
    await _create(client, customer_id, "D-2", name="1000 달성")

    assert await _codes(client, keyword="100%") == ["D-1"]


async def test_search_blank_keyword_is_no_condition(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, "D-1")
    await _create(client, customer_id, "D-2")

    assert await _codes(client, keyword="   ") == ["D-1", "D-2"]


async def test_search_accepts_keyword_of_exactly_100_chars(client: AsyncClient) -> None:
    response = await client.get(DEALS, params={"keyword": "a" * 100})

    assert response.status_code == 200


async def test_search_rejects_keyword_over_100_chars(client: AsyncClient) -> None:
    response = await client.get(DEALS, params={"keyword": "a" * 101})

    assert response.status_code == 422


async def test_search_rejects_malformed_customer_id(client: AsyncClient) -> None:
    response = await client.get(DEALS, params={"customer_id": "abc"})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_search_rejects_malformed_partner_id(client: AsyncClient) -> None:
    response = await client.get(DEALS, params={"partner_id": "abc"})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_search_by_customer_and_partner(client: AsyncClient) -> None:
    customer_a = await _customer_id(client, "고객A")
    customer_b = await _customer_id(client, "고객B")
    partner = await _partner_id(client)
    await _create(client, customer_a, "A-1", partner_id=partner)
    await _create(client, customer_a, "A-2")
    await _create(client, customer_b, "B-1", partner_id=partner)

    assert await _codes(client, customer_id=customer_a) == ["A-1", "A-2"]
    assert await _codes(client, partner_id=partner) == ["A-1", "B-1"]
    assert await _codes(client, customer_id=customer_a, partner_id=partner) == ["A-1"]


async def test_search_with_unknown_customer_or_partner_returns_empty_list(
    client: AsyncClient,
) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, "D-1")

    assert await _codes(client, customer_id=str(uuid4())) == []
    assert await _codes(client, partner_id=str(uuid4())) == []


async def test_search_by_owner_user_id_and_vendor_requires_exact_match(
    client: AsyncClient, owners: dict[str, str]
) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, "D-1", owner_user_id=owners["park"], vendor="SAP")
    await _create(client, customer_id, "D-2", owner_user_id=owners["park2"], vendor="SAP Korea")

    assert await _codes(client, owner_user_id=owners["park"]) == ["D-1"]
    assert await _codes(client, vendor="SAP") == ["D-1"]
    assert await _codes(client, owner_user_id=owners["park2"], vendor="SAP") == []


async def test_search_rejects_vendor_over_100_chars_as_request_validation(
    client: AsyncClient,
) -> None:
    response = await client.get(DEALS, params={"vendor": "a" * 101})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_search_accepts_vendor_of_exactly_100_chars(client: AsyncClient) -> None:
    response = await client.get(DEALS, params={"vendor": "a" * 100})

    assert response.status_code == 200


async def test_search_by_revenue_range(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, "D-0531", revenue_date="2026-05-31")
    await _create(client, customer_id, "D-0601", revenue_date="2026-06-01")
    await _create(client, customer_id, "D-0630", revenue_date="2026-06-30")
    await _create(client, customer_id, "D-0701", revenue_date="2026-07-01")

    june = await _codes(client, revenue_from="2026-06-01", revenue_to="2026-07-01")
    only_from = await _codes(client, revenue_from="2026-06-30")
    only_to = await _codes(client, revenue_to="2026-06-01")

    assert june == ["D-0601", "D-0630"]  # 6월 30일 포함, 7월 1일 제외
    assert only_from == ["D-0630", "D-0701"]
    assert only_to == ["D-0531"]


async def test_search_rejects_revenue_from_not_before_to(client: AsyncClient) -> None:
    same = await client.get(
        DEALS, params={"revenue_from": "2026-06-01", "revenue_to": "2026-06-01"}
    )
    reversed_ = await client.get(
        DEALS, params={"revenue_from": "2026-07-01", "revenue_to": "2026-06-01"}
    )

    for response in (same, reversed_):
        assert response.status_code == 422
        assert response.json()["type"].endswith("invalid-value")


async def test_search_rejects_malformed_revenue_date(client: AsyncClient) -> None:
    from_ = await client.get(DEALS, params={"revenue_from": "2026-13-01"})
    to = await client.get(DEALS, params={"revenue_to": "yesterday"})

    for response in (from_, to):
        assert response.status_code == 422
        assert response.json()["type"].endswith("request-validation")


async def test_search_combines_conditions_with_and_and_keeps_paging(
    client: AsyncClient, owners: dict[str, str]
) -> None:
    customer_a = await _customer_id(client, "고객A")
    customer_b = await _customer_id(client, "고객B")
    june, x, y = "2026-06-10", owners["x"], owners["y"]
    await _create(client, customer_a, "HIT-1", owner_user_id=x, revenue_date=june)
    await _create(client, customer_b, "OTHER-CUSTOMER", owner_user_id=x, revenue_date=june)
    await _create(client, customer_a, "HIT-2", owner_user_id=x, revenue_date=june)
    await _create(client, customer_a, "OTHER-OWNER", owner_user_id=y, revenue_date=june)

    params = {"customer_id": customer_a, "owner_user_id": x, "revenue_from": "2026-06-01"}

    assert await _codes(client, **params) == ["HIT-1", "HIT-2"]
    assert await _codes(client, **params, offset=1, limit=1) == ["HIT-2"]


async def test_search_rejects_unknown_query_parameter(client: AsyncClient) -> None:
    response = await client.get(DEALS, params={"foo": "1"})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_search_conditions_do_not_change_response_shape(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, "D-1")

    body = (await client.get(DEALS, params={"keyword": "d-1", "limit": 10})).json()

    assert set(body) == {"items", "offset", "limit"}
    assert (body["offset"], body["limit"]) == (0, 10)
