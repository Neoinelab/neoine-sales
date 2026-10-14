"""Deal 담당자는 사용자 id로 요청하고 UserRef로 응답한다(AC4·8·10, T17·T22)."""

from typing import TYPE_CHECKING
from uuid import uuid4

from app.domain.auth.principal import Role
from tests.e2e.payloads import customer_payload, deal_payload
from tests.support.user_ids import OWNER_ID

if TYPE_CHECKING:
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

DEALS = "/api/v1/deals"


async def _customer_id(client: AsyncClient) -> str:
    response = await client.post("/api/v1/customers", json=customer_payload())
    return str(response.json()["id"])


async def _create(client: AsyncClient, customer_id: str, **overrides: object) -> dict[str, object]:
    response = await client.post(DEALS, json=deal_payload(customer_id, **overrides))
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


async def test_response_carries_the_owner_as_a_user_ref_with_a_label(
    client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("hong", Role.SALES)
    hong = await use_cases.user_id_of("hong")
    customer_id = await _customer_id(client)

    body = await _create(client, customer_id, owner_user_id=str(hong))

    assert body["owner"] == {
        "id": str(hong),
        "name": "hong",
        "resigned": False,
        "label": "hong",
    }
    assert "owner_user_id" not in body
    assert "registered_by_user_id" not in body  # 등록자는 노출하지 않는다


async def test_the_default_payload_owner_is_the_seeded_owner_user(client: AsyncClient) -> None:
    body = await _create(client, await _customer_id(client))

    owner = body["owner"]
    assert isinstance(owner, dict)
    assert (owner["id"], owner["name"]) == (str(OWNER_ID), "owner")
    assert "login_id" not in owner


async def test_a_resigned_owner_is_shown_with_the_resigned_label(
    client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("hong", Role.SALES)
    hong = await use_cases.user_id_of("hong")
    customer_id = await _customer_id(client)
    created = await _create(client, customer_id, owner_user_id=str(hong))
    await use_cases.resign_user(hong)

    body = (await client.get(f"{DEALS}/{created['id']}")).json()

    assert body["owner"]["resigned"] is True
    assert body["owner"]["label"] == "hong(퇴사)"
    assert body["owner"]["id"] == str(hong)


async def test_owner_user_id_is_required_and_the_free_text_owner_is_not_accepted(
    client: AsyncClient,
) -> None:
    customer_id = await _customer_id(client)
    payload = deal_payload(customer_id)
    without_owner = {k: v for k, v in payload.items() if k != "owner_user_id"}

    missing = await client.post(DEALS, json=without_owner)
    legacy = await client.post(DEALS, json={**without_owner, "owner": "박영업"})

    assert missing.status_code == 422
    assert missing.json()["type"].endswith("request-validation")
    assert legacy.status_code == 422


async def test_malformed_owner_user_id_is_a_request_validation_error(client: AsyncClient) -> None:
    customer_id = await _customer_id(client)

    response = await client.post(DEALS, json=deal_payload(customer_id, owner_user_id="not-a-uuid"))

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_unknown_owner_is_a_422_invalid_reference_and_nothing_is_created(
    client: AsyncClient,
) -> None:
    customer_id = await _customer_id(client)

    response = await client.post(DEALS, json=deal_payload(customer_id, owner_user_id=str(uuid4())))

    assert response.status_code == 422
    assert response.json()["type"].endswith("invalid-reference")
    assert (await client.get(DEALS)).json()["items"] == []


async def test_resigned_owner_cannot_be_assigned_to_a_new_deal(
    client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("gone", Role.SALES)
    gone = await use_cases.user_id_of("gone")
    await use_cases.resign_user(gone)
    customer_id = await _customer_id(client)

    response = await client.post(DEALS, json=deal_payload(customer_id, owner_user_id=str(gone)))

    assert response.status_code == 422
    assert response.json()["type"].endswith("invalid-reference")


async def test_update_keeping_a_resigned_owner_is_allowed_but_switching_to_one_is_not(
    client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("hong", Role.SALES)
    hong = await use_cases.user_id_of("hong")
    customer_id = await _customer_id(client)
    created = await _create(client, customer_id, owner_user_id=str(hong))
    await use_cases.resign_user(hong)
    other = await _create(client, customer_id, code="D-2")

    kept = await client.put(
        f"{DEALS}/{created['id']}",
        json=deal_payload(customer_id, owner_user_id=str(hong), name="이름만 수정"),
    )
    switched = await client.put(
        f"{DEALS}/{other['id']}",
        json=deal_payload(customer_id, code="D-2", owner_user_id=str(hong)),
    )

    assert kept.status_code == 200
    assert kept.json()["owner"]["label"] == "hong(퇴사)"
    assert switched.status_code == 422
    assert switched.json()["type"].endswith("invalid-reference")
