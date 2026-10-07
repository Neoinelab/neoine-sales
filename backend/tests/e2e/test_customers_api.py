from typing import TYPE_CHECKING
from uuid import uuid4

from tests.e2e.payloads import customer_payload, deal_payload

if TYPE_CHECKING:
    from httpx import AsyncClient

BASE = "/api/v1/customers"
PROBLEM = "application/problem+json"


async def _create(client: AsyncClient, **overrides: object) -> dict[str, object]:
    response = await client.post(BASE, json=customer_payload(**overrides))
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


async def test_create_returns_201_with_location_and_the_stored_values(client: AsyncClient) -> None:
    response = await client.post(BASE, json=customer_payload())

    assert response.status_code == 201
    body = response.json()
    assert response.headers["location"] == f"{BASE}/{body['id']}"
    assert body["company_name"] == "네오인"
    assert body["email"] == "kim@neoine.example"  # 도메인이 정규화한 값
    assert body["employee_count"] == 120
    assert body["created_at"].startswith("2026-01-01T09:00:00")
    assert body["updated_at"] == body["created_at"]


async def test_create_with_only_required_fields_leaves_optional_ones_empty(
    client: AsyncClient,
) -> None:
    response = await client.post(BASE, json={"company_name": "회사", "contact_name": "담당"})

    body = response.json()
    assert response.status_code == 201
    assert body["contact_title"] is None
    assert body["email"] is None
    assert body["phone"] is None
    assert body["employee_count"] is None
    assert body["notes"] == ""


async def test_invalid_email_is_a_422_problem_and_nothing_is_stored(client: AsyncClient) -> None:
    response = await client.post(BASE, json=customer_payload(email="not-an-email"))

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM)
    problem = response.json()
    assert problem["status"] == 422
    assert problem["type"].endswith("invalid-value")
    assert "이메일" in problem["detail"]
    assert (await client.get(BASE)).json()["items"] == []


async def test_missing_required_field_is_a_422_problem_with_error_locations(
    client: AsyncClient,
) -> None:
    response = await client.post(BASE, json={"contact_name": "담당"})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM)
    problem = response.json()
    assert problem["type"].endswith("request-validation")
    assert any(error["loc"][-1] == "company_name" for error in problem["errors"])


async def test_unknown_fields_are_rejected(client: AsyncClient) -> None:
    response = await client.post(BASE, json=customer_payload(unexpected="x"))

    assert response.status_code == 422


async def test_get_returns_the_customer(client: AsyncClient) -> None:
    created = await _create(client)

    response = await client.get(f"{BASE}/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


async def test_get_unknown_customer_is_a_404_problem(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/{uuid4()}")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json()["type"].endswith("not-found")


async def test_malformed_id_is_a_422(client: AsyncClient) -> None:
    assert (await client.get(f"{BASE}/not-a-uuid")).status_code == 422


async def test_list_pages_in_creation_order(client: AsyncClient) -> None:
    ids = []
    for number in range(3):
        created = await _create(client, company_name=f"고객{number}")
        ids.append(created["id"])

    page = (await client.get(BASE, params={"offset": 1, "limit": 2})).json()

    assert [item["id"] for item in page["items"]] == ids[1:]
    assert page["offset"] == 1
    assert page["limit"] == 2


async def test_list_rejects_invalid_paging(client: AsyncClient) -> None:
    assert (await client.get(BASE, params={"limit": 0})).status_code == 422
    assert (await client.get(BASE, params={"limit": 201})).status_code == 422
    assert (await client.get(BASE, params={"offset": -1})).status_code == 422


async def test_update_replaces_the_values(client: AsyncClient) -> None:
    created = await _create(client)

    response = await client.put(
        f"{BASE}/{created['id']}",
        json=customer_payload(company_name="새 회사", employee_count=None),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["company_name"] == "새 회사"
    assert body["employee_count"] is None
    assert body["id"] == created["id"]
    assert (await client.get(f"{BASE}/{created['id']}")).json() == body


async def test_update_with_invalid_values_is_a_422_and_changes_nothing(
    client: AsyncClient,
) -> None:
    created = await _create(client)

    response = await client.put(f"{BASE}/{created['id']}", json=customer_payload(company_name="  "))

    assert response.status_code == 422
    assert (await client.get(f"{BASE}/{created['id']}")).json()["company_name"] == "네오인"


async def test_update_unknown_customer_is_a_404(client: AsyncClient) -> None:
    response = await client.put(f"{BASE}/{uuid4()}", json=customer_payload())

    assert response.status_code == 404


async def test_delete_returns_204_and_hides_the_customer(client: AsyncClient) -> None:
    created = await _create(client)

    response = await client.delete(f"{BASE}/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert (await client.get(f"{BASE}/{created['id']}")).status_code == 404
    assert (await client.get(BASE)).json()["items"] == []


async def test_delete_unknown_or_already_deleted_customer_is_a_404(client: AsyncClient) -> None:
    created = await _create(client)
    await client.delete(f"{BASE}/{created['id']}")

    assert (await client.delete(f"{BASE}/{created['id']}")).status_code == 404
    assert (await client.delete(f"{BASE}/{uuid4()}")).status_code == 404


async def test_customer_with_an_active_deal_cannot_be_deleted(client: AsyncClient) -> None:
    created = await _create(client)
    deal = await client.post("/api/v1/deals", json=deal_payload(str(created["id"])))

    blocked = await client.delete(f"{BASE}/{created['id']}")
    await client.delete(f"/api/v1/deals/{deal.json()['id']}")
    allowed = await client.delete(f"{BASE}/{created['id']}")

    assert blocked.status_code == 409
    assert blocked.json()["type"].endswith("invalid-state")
    assert allowed.status_code == 204
