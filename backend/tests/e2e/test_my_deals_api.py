"""내 딜(mine): 등록한 사용자의 subject 기준으로 목록·파이프라인을 좁힌다(Fake UoW, 다중 사용자)."""

from typing import TYPE_CHECKING
from uuid import UUID

from app.main import create_app
from tests.e2e.conftest import make_settings
from tests.e2e.payloads import customer_payload, deal_payload
from tests.factories import make_deal_input
from tests.fakes.use_cases import FakeUseCases

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from httpx import AsyncClient

    ClientFor = Callable[[str], Awaitable[AsyncClient]]

DEALS = "/api/v1/deals"
PIPELINE = f"{DEALS}/pipeline"


async def _customer_id(client: AsyncClient) -> str:
    response = await client.post("/api/v1/customers", json=customer_payload())
    return str(response.json()["id"])


async def _register(client: AsyncClient, customer_id: str, code: str, **overrides: object) -> str:
    response = await client.post(DEALS, json=deal_payload(customer_id, code=code, **overrides))
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _codes(client: AsyncClient, **params: object) -> list[str]:
    response = await client.get(DEALS, params=params)  # type: ignore[arg-type]
    assert response.status_code == 200, response.text
    return [item["code"] for item in response.json()["items"]]


async def _prospecting_count(client: AsyncClient, **params: object) -> int:
    response = await client.get(PIPELINE, params=params)  # type: ignore[arg-type]
    assert response.status_code == 200, response.text
    return int(response.json()["stages"][0]["deal_count"])


async def test_registered_deal_is_mine(client_for: ClientFor) -> None:
    alice = await client_for("alice")
    await _register(alice, await _customer_id(alice), "A-1")

    assert await _codes(alice, mine="true") == ["A-1"]


async def test_mine_returns_only_the_current_users_deals(client_for: ClientFor) -> None:
    alice, bob = await client_for("alice"), await client_for("bob")
    customer_id = await _customer_id(alice)
    await _register(alice, customer_id, "A-1")
    await _register(bob, customer_id, "B-1")
    await _register(alice, customer_id, "A-2")

    assert await _codes(alice, mine="true") == ["A-1", "A-2"]
    assert await _codes(bob, mine="true") == ["B-1"]


async def test_without_mine_lists_everyones_deals(client_for: ClientFor) -> None:
    alice, bob = await client_for("alice"), await client_for("bob")
    customer_id = await _customer_id(alice)
    await _register(alice, customer_id, "A-1")
    await _register(bob, customer_id, "B-1")

    assert await _codes(alice) == ["A-1", "B-1"]
    assert await _codes(bob, mine="false") == ["A-1", "B-1"]


async def test_mine_for_a_user_without_deals_is_an_empty_page(client_for: ClientFor) -> None:
    alice, carol = await client_for("alice"), await client_for("carol")
    await _register(alice, await _customer_id(alice), "A-1")

    response = await carol.get(DEALS, params={"mine": "true"})

    assert response.status_code == 200
    assert response.json() == {"items": [], "offset": 0, "limit": 50}


async def test_mine_combines_with_other_conditions_and_paging(client_for: ClientFor) -> None:
    alice, bob = await client_for("alice"), await client_for("bob")
    customer_id = await _customer_id(alice)
    await _register(alice, customer_id, "ERP-1")
    await _register(alice, customer_id, "ERP-2")
    await _register(alice, customer_id, "CRM-1", name="CRM 구축")
    await _register(bob, customer_id, "ERP-3")
    moved = await _register(alice, customer_id, "ERP-4")
    assert (
        await alice.post(f"{DEALS}/{moved}/stage", json={"stage": "lost", "reason": "x"})
    ).status_code == 200

    assert await _codes(alice, mine="true", keyword="erp") == ["ERP-1", "ERP-2", "ERP-4"]
    assert await _codes(alice, mine="true", stage="lost") == ["ERP-4"]
    assert await _codes(alice, mine="true", offset=1, limit=2) == ["ERP-2", "CRM-1"]
    assert await _codes(bob, mine="true", keyword="crm") == []


async def test_mine_excludes_deleted_deals(client_for: ClientFor) -> None:
    alice = await client_for("alice")
    customer_id = await _customer_id(alice)
    await _register(alice, customer_id, "KEEP")
    gone = await _register(alice, customer_id, "GONE")
    await alice.delete(f"{DEALS}/{gone}")

    assert await _codes(alice, mine="true") == ["KEEP"]


async def test_deals_registered_before_owner_tracking_are_never_mine(
    client_for: ClientFor, use_cases: FakeUseCases
) -> None:
    alice = await client_for("alice")
    customer_id = await _customer_id(alice)
    legacy = make_deal_input(UUID(customer_id), code="OLD-1")
    await use_cases.register_deal().execute(legacy)  # owner_user_id 없이 등록된 기존 딜
    await _register(alice, customer_id, "A-1")

    assert await _codes(alice, mine="true") == ["A-1"]
    assert await _codes(alice) == ["OLD-1", "A-1"]
    assert await _prospecting_count(alice, mine="true") == 1
    assert await _prospecting_count(alice) == 2


async def test_owner_user_id_cannot_be_sent_in_the_body(client_for: ClientFor) -> None:
    alice = await client_for("alice")
    customer_id = await _customer_id(alice)

    response = await alice.post(DEALS, json=deal_payload(customer_id, owner_user_id="bob"))

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")
    assert await _codes(alice) == []


async def test_owner_user_id_cannot_be_sent_in_a_put_body(client_for: ClientFor) -> None:
    alice = await client_for("alice")
    customer_id = await _customer_id(alice)
    deal_id = await _register(alice, customer_id, "A-1")

    response = await alice.put(
        f"{DEALS}/{deal_id}", json=deal_payload(customer_id, code="A-1", owner_user_id="bob")
    )

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_responses_do_not_expose_owner_user_id(client_for: ClientFor) -> None:
    alice = await client_for("alice")
    customer_id = await _customer_id(alice)
    created = await alice.post(DEALS, json=deal_payload(customer_id, code="A-1"))
    deal_id = created.json()["id"]

    bodies = [
        created.json(),
        (await alice.get(f"{DEALS}/{deal_id}")).json(),
        (await alice.get(f"{DEALS}/by-code/A-1")).json(),
        (await alice.get(DEALS, params={"mine": "true"})).json()["items"][0],
        (await alice.put(f"{DEALS}/{deal_id}", json=deal_payload(customer_id, code="A-1"))).json(),
    ]

    for body in bodies:
        assert "owner_user_id" not in body
        assert "alice" not in str(body)


async def test_another_user_editing_does_not_take_ownership(client_for: ClientFor) -> None:
    alice, bob = await client_for("alice"), await client_for("bob")
    customer_id = await _customer_id(alice)
    deal_id = await _register(alice, customer_id, "A-1")

    edited = await bob.put(
        f"{DEALS}/{deal_id}", json=deal_payload(customer_id, code="A-1", name="Bob이 수정")
    )

    assert edited.status_code == 200
    assert await _codes(alice, mine="true") == ["A-1"]
    assert await _codes(bob, mine="true") == []


async def test_another_user_changing_the_stage_does_not_take_ownership(
    client_for: ClientFor,
) -> None:
    alice, bob = await client_for("alice"), await client_for("bob")
    deal_id = await _register(alice, await _customer_id(alice), "A-1")

    moved = await bob.post(f"{DEALS}/{deal_id}/stage", json={"stage": "introduction"})

    assert moved.status_code == 200
    assert await _codes(alice, mine="true", stage="introduction") == ["A-1"]
    assert await _codes(bob, mine="true") == []


async def test_mine_must_be_a_boolean(client_for: ClientFor) -> None:
    alice = await client_for("alice")

    for path in (DEALS, PIPELINE):
        response = await alice.get(path, params={"mine": "maybe"})

        assert response.status_code == 422, path
        assert response.json()["type"].endswith("request-validation")


async def test_owner_user_id_query_parameter_is_rejected(client_for: ClientFor) -> None:
    alice = await client_for("alice")

    for path in (DEALS, PIPELINE):
        response = await alice.get(path, params={"owner_user_id": "bob"})

        assert response.status_code == 422, path
        assert response.json()["type"].endswith("request-validation")


async def test_mine_requires_login(anonymous_client: AsyncClient) -> None:
    for path in (DEALS, PIPELINE):
        response = await anonymous_client.get(path, params={"mine": "true"})

        assert response.status_code == 401, path
        assert response.json()["type"].endswith("unauthenticated")


async def test_pipeline_mine_counts_only_my_deals(client_for: ClientFor) -> None:
    alice, bob = await client_for("alice"), await client_for("bob")
    customer_id = await _customer_id(alice)
    await _register(alice, customer_id, "A-1", revenue_amount="10")
    kept = await _register(alice, customer_id, "A-2", revenue_amount="5")
    await _register(bob, customer_id, "B-1", revenue_amount="1000")
    await alice.post(f"{DEALS}/{kept}/stage", json={"stage": "lost", "reason": "x"})

    mine = {
        s["stage"]: s for s in (await alice.get(PIPELINE, params={"mine": "true"})).json()["stages"]
    }
    everyone = {s["stage"]: s for s in (await alice.get(PIPELINE)).json()["stages"]}
    bobs = {
        s["stage"]: s for s in (await bob.get(PIPELINE, params={"mine": "true"})).json()["stages"]
    }

    assert mine["prospecting"]["deal_count"] == 1
    assert mine["prospecting"]["totals"] == [{"currency": "KRW", "amount": "10"}]
    assert mine["lost"]["totals"] == [{"currency": "KRW", "amount": "5"}]
    assert everyone["prospecting"]["deal_count"] == 2
    assert bobs["prospecting"]["totals"] == [{"currency": "KRW", "amount": "1000"}]
    assert bobs["lost"]["deal_count"] == 0


async def test_pipeline_mine_for_a_user_without_deals_lists_all_stages_with_zero(
    client_for: ClientFor,
) -> None:
    alice, carol = await client_for("alice"), await client_for("carol")
    await _register(alice, await _customer_id(alice), "A-1")

    stages = (await carol.get(PIPELINE, params={"mine": "true"})).json()["stages"]

    assert len(stages) == 8
    assert all(s["deal_count"] == 0 and s["totals"] == [] for s in stages)


def test_openapi_documents_mine_but_not_owner_user_id() -> None:
    schema = create_app(settings=make_settings(), use_cases=FakeUseCases()).openapi()

    for path in (DEALS, PIPELINE):
        params = {p["name"]: p for p in schema["paths"][path]["get"]["parameters"]}
        assert params["mine"]["schema"]["type"] == "boolean", path
        assert params["mine"]["schema"]["default"] is False, path
        assert not params["mine"].get("required"), path
        assert "owner_user_id" not in params, path
    components = schema["components"]["schemas"]
    assert "owner_user_id" not in components["DealResponse"]["properties"]
    assert "owner_user_id" not in components["DealRequest"]["properties"]
