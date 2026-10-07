from typing import TYPE_CHECKING
from uuid import uuid4

from tests.e2e.payloads import customer_payload, deal_payload, partner_payload

if TYPE_CHECKING:
    from httpx import AsyncClient

BASE = "/api/v1/partners"
PROBLEM = "application/problem+json"


async def _create(client: AsyncClient, **overrides: object) -> dict[str, object]:
    response = await client.post(BASE, json=partner_payload(**overrides))
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


async def test_create_returns_201_with_location(client: AsyncClient) -> None:
    response = await client.post(BASE, json=partner_payload())

    body = response.json()
    assert response.status_code == 201
    assert response.headers["location"] == f"{BASE}/{body['id']}"
    assert body["company_name"] == "한빛파트너스"
    assert body["contact_name"] == "이영희"
    assert body["email"] == "lee@hanbit.example"


async def test_invalid_phone_is_a_422_problem(client: AsyncClient) -> None:
    response = await client.post(BASE, json=partner_payload(phone="abc"))

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json()["type"].endswith("invalid-value")


async def test_get_and_unknown_partner(client: AsyncClient) -> None:
    created = await _create(client)

    assert (await client.get(f"{BASE}/{created['id']}")).json() == created
    unknown = await client.get(f"{BASE}/{uuid4()}")
    assert unknown.status_code == 404
    assert unknown.json()["type"].endswith("not-found")


async def test_list_pages_and_excludes_deleted(client: AsyncClient) -> None:
    ids = [(await _create(client, company_name=f"파트너{n}"))["id"] for n in range(4)]
    await client.delete(f"{BASE}/{ids[0]}")

    page = (await client.get(BASE, params={"offset": 1, "limit": 2})).json()

    assert [item["id"] for item in page["items"]] == ids[2:]


async def test_update_replaces_values_and_unknown_is_404(client: AsyncClient) -> None:
    created = await _create(client)

    updated = await client.put(
        f"{BASE}/{created['id']}", json=partner_payload(company_name="새 파트너", email=None)
    )

    assert updated.status_code == 200
    assert updated.json()["company_name"] == "새 파트너"
    assert updated.json()["email"] is None
    assert (await client.put(f"{BASE}/{uuid4()}", json=partner_payload())).status_code == 404


async def test_delete_hides_the_partner(client: AsyncClient) -> None:
    created = await _create(client)

    assert (await client.delete(f"{BASE}/{created['id']}")).status_code == 204
    assert (await client.get(f"{BASE}/{created['id']}")).status_code == 404
    assert (await client.delete(f"{BASE}/{created['id']}")).status_code == 404


async def test_partner_with_an_active_deal_cannot_be_deleted(client: AsyncClient) -> None:
    partner = await _create(client)
    customer = (await client.post("/api/v1/customers", json=customer_payload())).json()
    await client.post(
        "/api/v1/deals", json=deal_payload(customer["id"], partner_id=str(partner["id"]))
    )

    response = await client.delete(f"{BASE}/{partner['id']}")

    assert response.status_code == 409
    assert response.json()["type"].endswith("invalid-state")
