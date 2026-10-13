from typing import TYPE_CHECKING
from uuid import uuid4

from tests.e2e.payloads import customer_payload, deal_payload, partner_payload

if TYPE_CHECKING:
    from httpx import AsyncClient

DEALS = "/api/v1/deals"
PROBLEM = "application/problem+json"


async def _customer_id(client: AsyncClient) -> str:
    response = await client.post("/api/v1/customers", json=customer_payload())
    return str(response.json()["id"])


async def _partner_id(client: AsyncClient) -> str:
    response = await client.post("/api/v1/partners", json=partner_payload())
    return str(response.json()["id"])


async def _create(client: AsyncClient, customer_id: str, **overrides: object) -> dict[str, object]:
    response = await client.post(DEALS, json=deal_payload(customer_id, **overrides))
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


async def test_create_returns_201_with_location_and_normalized_values(
    client: AsyncClient,
) -> None:
    customer_id = await _customer_id(client)

    response = await client.post(DEALS, json=deal_payload(customer_id))

    body = response.json()
    assert response.status_code == 201
    assert response.headers["location"] == f"{DEALS}/{body['id']}"
    assert body["code"] == "DEAL-001"  # 대문자로 정규화
    assert body["customer_id"] == customer_id
    assert body["partner_id"] is None
    assert body["revenue_amount"] == "150000000"  # 금액은 문자열로 정밀도를 보존한다
    assert body["revenue_currency"] == "KRW"
    assert body["revenue_date"] == "2026-06-30"


async def test_amount_keeps_four_decimal_places(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)

    body = await _create(client, customer_id, revenue_amount="1234567.8912", revenue_currency="USD")

    assert body["revenue_amount"] == "1234567.8912"
    assert body["revenue_currency"] == "USD"


async def test_create_with_an_existing_partner(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    partner_id = await _partner_id(client)

    body = await _create(client, customer_id, partner_id=partner_id)

    assert body["partner_id"] == partner_id


async def test_unknown_customer_is_a_422_invalid_reference(client: AsyncClient) -> None:
    response = await client.post(DEALS, json=deal_payload(str(uuid4())))

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json()["type"].endswith("invalid-reference")
    assert (await client.get(DEALS)).json()["items"] == []


async def test_unknown_partner_is_a_422_invalid_reference(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)

    response = await client.post(DEALS, json=deal_payload(customer_id, partner_id=str(uuid4())))

    assert response.status_code == 422
    assert response.json()["type"].endswith("invalid-reference")


async def test_duplicate_code_is_a_409_problem(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id)

    response = await client.post(DEALS, json=deal_payload(customer_id, code="DEAL-001"))

    assert response.status_code == 409
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json()["type"].endswith("already-exists")


async def test_negative_amount_is_a_422(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)

    response = await client.post(DEALS, json=deal_payload(customer_id, revenue_amount="-1"))

    assert response.status_code == 422
    assert response.json()["type"].endswith("invalid-value")


async def test_malformed_date_is_a_request_validation_error(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)

    response = await client.post(DEALS, json=deal_payload(customer_id, revenue_date="30/06/2026"))

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_get_by_id_and_by_code(client: AsyncClient) -> None:
    created = await _create(client, await _customer_id(client))

    assert (await client.get(f"{DEALS}/{created['id']}")).json() == created
    assert (await client.get(f"{DEALS}/by-code/Deal-001")).json() == created


async def test_unknown_deal_is_a_404(client: AsyncClient) -> None:
    assert (await client.get(f"{DEALS}/{uuid4()}")).status_code == 404
    assert (await client.get(f"{DEALS}/by-code/NOPE-1")).status_code == 404


async def test_malformed_code_in_the_path_is_a_422(client: AsyncClient) -> None:
    assert (await client.get(f"{DEALS}/by-code/-bad")).status_code == 422


async def test_list_pages_in_creation_order_and_excludes_deleted(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    ids = [(await _create(client, customer_id, code=f"D-{n}"))["id"] for n in range(4)]
    await client.delete(f"{DEALS}/{ids[0]}")

    page = (await client.get(DEALS, params={"offset": 1, "limit": 2})).json()

    assert [item["id"] for item in page["items"]] == ids[2:]


async def test_update_replaces_values_and_rechecks_references(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    created = await _create(client, customer_id)

    updated = await client.put(
        f"{DEALS}/{created['id']}",
        json=deal_payload(customer_id, name="확장 프로젝트", vendor="Oracle"),
    )
    unknown_customer = await client.put(
        f"{DEALS}/{created['id']}", json=deal_payload(str(uuid4()), name="바뀌면 안 됨")
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "확장 프로젝트"
    assert unknown_customer.status_code == 422
    assert (await client.get(f"{DEALS}/{created['id']}")).json()["name"] == "확장 프로젝트"


async def test_update_to_an_unknown_partner_is_a_422_and_keeps_the_deal(
    client: AsyncClient,
) -> None:
    customer_id = await _customer_id(client)
    created = await _create(client, customer_id)

    response = await client.put(
        f"{DEALS}/{created['id']}",
        json=deal_payload(customer_id, partner_id=str(uuid4()), name="바뀌면 안 됨"),
    )

    assert response.status_code == 422
    assert response.json()["type"].endswith("invalid-reference")
    assert (await client.get(f"{DEALS}/{created['id']}")).json()["name"] == created["name"]


async def test_update_to_another_deals_code_is_a_409(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)
    await _create(client, customer_id, code="D-1")
    second = await _create(client, customer_id, code="D-2")

    response = await client.put(
        f"{DEALS}/{second['id']}", json=deal_payload(customer_id, code="D-1")
    )

    assert response.status_code == 409


async def test_delete_removes_the_deal_physically_and_frees_its_code(
    client: AsyncClient,
) -> None:
    customer_id = await _customer_id(client)
    created = await _create(client, customer_id)

    assert (await client.delete(f"{DEALS}/{created['id']}")).status_code == 204
    assert (await client.get(f"{DEALS}/{created['id']}")).status_code == 404
    assert (await client.get(f"{DEALS}/by-code/deal-001")).status_code == 404
    assert (await client.delete(f"{DEALS}/{created['id']}")).status_code == 404
    reuse = await client.post(DEALS, json=deal_payload(customer_id))
    assert reuse.status_code == 201
    assert reuse.json()["id"] != created["id"]
