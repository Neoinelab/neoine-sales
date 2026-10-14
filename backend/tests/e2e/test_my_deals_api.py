"""내 딜(mine): 담당자(owner_user_id)가 로그인 사용자인 딜로 목록·파이프라인을 좁힌다(AC12).

등록자(registered_by_user_id)는 감사용으로만 남고 mine 조건에 쓰이지 않는다.
Fake UoW, 다중 사용자.
"""

from typing import TYPE_CHECKING

from app.main import create_app
from tests.e2e.conftest import make_settings
from tests.e2e.payloads import customer_payload, deal_payload
from tests.e2e.payloads_auth import ME
from tests.fakes.use_cases import FakeUseCases

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from httpx import AsyncClient

    ClientFor = Callable[[str], Awaitable[AsyncClient]]

DEALS = "/api/v1/deals"
PIPELINE = f"{DEALS}/pipeline"


async def _me(client: AsyncClient) -> str:
    return str((await client.get(ME)).json()["user_id"])


async def _customer_id(client: AsyncClient) -> str:
    response = await client.post("/api/v1/customers", json=customer_payload())
    return str(response.json()["id"])


async def _register(
    client: AsyncClient, customer_id: str, code: str, owner: str, **overrides: object
) -> str:
    payload = deal_payload(customer_id, code=code, owner_user_id=owner, **overrides)
    response = await client.post(DEALS, json=payload)
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


async def test_a_deal_whose_owner_is_me_is_mine(client_for: ClientFor) -> None:
    alice = await client_for("alice")
    await _register(alice, await _customer_id(alice), "A-1", await _me(alice))

    assert await _codes(alice, mine="true") == ["A-1"]


async def test_mine_follows_the_owner_not_the_registrant(client_for: ClientFor) -> None:
    alice, bob = await client_for("alice"), await client_for("bob")
    customer_id = await _customer_id(alice)
    a, b = await _me(alice), await _me(bob)
    await _register(alice, customer_id, "OWN-BY-ALICE", a)
    await _register(alice, customer_id, "BOBS-BUT-ALICE-REGISTERED", b)  # alice가 등록, 담당자 bob
    await _register(bob, customer_id, "ALICES-BUT-BOB-REGISTERED", a)  # bob이 등록, 담당자 alice

    assert await _codes(alice, mine="true") == ["OWN-BY-ALICE", "ALICES-BUT-BOB-REGISTERED"]
    assert await _codes(bob, mine="true") == ["BOBS-BUT-ALICE-REGISTERED"]


async def test_without_mine_lists_everyones_deals(client_for: ClientFor) -> None:
    alice, bob = await client_for("alice"), await client_for("bob")
    customer_id = await _customer_id(alice)
    await _register(alice, customer_id, "A-1", await _me(alice))
    await _register(bob, customer_id, "B-1", await _me(bob))

    assert await _codes(alice) == ["A-1", "B-1"]
    assert await _codes(bob, mine="false") == ["A-1", "B-1"]


async def test_mine_for_a_user_without_owned_deals_is_an_empty_page(client_for: ClientFor) -> None:
    alice, carol = await client_for("alice"), await client_for("carol")
    await _register(alice, await _customer_id(alice), "A-1", await _me(alice))

    response = await carol.get(DEALS, params={"mine": "true"})

    assert response.status_code == 200
    assert response.json() == {"items": [], "offset": 0, "limit": 50}


async def test_deals_with_the_default_owner_are_nobodys_mine(client_for: ClientFor) -> None:
    alice = await client_for("alice")
    customer_id = await _customer_id(alice)
    response = await alice.post(DEALS, json=deal_payload(customer_id, code="DEFAULT-OWNER"))
    assert response.status_code == 201
    await _register(alice, customer_id, "A-1", await _me(alice))

    assert await _codes(alice, mine="true") == ["A-1"]
    assert await _codes(alice) == ["DEFAULT-OWNER", "A-1"]
    assert await _prospecting_count(alice, mine="true") == 1
    assert await _prospecting_count(alice) == 2


async def test_mine_combines_with_other_conditions_and_paging(client_for: ClientFor) -> None:
    alice, bob = await client_for("alice"), await client_for("bob")
    customer_id = await _customer_id(alice)
    a, b = await _me(alice), await _me(bob)
    await _register(alice, customer_id, "ERP-1", a)
    await _register(alice, customer_id, "ERP-2", a)
    await _register(alice, customer_id, "CRM-1", a, name="CRM 구축")
    await _register(bob, customer_id, "ERP-3", b)
    moved = await _register(alice, customer_id, "ERP-4", a)
    assert (
        await alice.post(f"{DEALS}/{moved}/stage", json={"stage": "lost", "reason": "x"})
    ).status_code == 200

    assert await _codes(alice, mine="true", keyword="erp") == ["ERP-1", "ERP-2", "ERP-4"]
    assert await _codes(alice, mine="true", stage="lost") == ["ERP-4"]
    assert await _codes(alice, mine="true", offset=1, limit=2) == ["ERP-2", "CRM-1"]
    assert await _codes(bob, mine="true", keyword="crm") == []


async def test_mine_excludes_deleted_deals(client_for: ClientFor) -> None:
    alice = await client_for("alice")
    customer_id, a = await _customer_id(alice), await _me(alice)
    await _register(alice, customer_id, "KEEP", a)
    gone = await _register(alice, customer_id, "GONE", a)
    await alice.delete(f"{DEALS}/{gone}")

    assert await _codes(alice, mine="true") == ["KEEP"]


async def test_changing_the_owner_moves_the_deal_between_mine_lists(client_for: ClientFor) -> None:
    alice, bob = await client_for("alice"), await client_for("bob")
    customer_id = await _customer_id(alice)
    a, b = await _me(alice), await _me(bob)
    deal_id = await _register(alice, customer_id, "A-1", a)

    handed_over = await alice.put(
        f"{DEALS}/{deal_id}", json=deal_payload(customer_id, code="A-1", owner_user_id=b)
    )

    assert handed_over.status_code == 200
    assert await _codes(alice, mine="true") == []
    assert await _codes(bob, mine="true") == ["A-1"]


async def test_another_user_editing_other_fields_does_not_change_the_owner(
    client_for: ClientFor,
) -> None:
    alice, bob = await client_for("alice"), await client_for("bob")
    customer_id, a = await _customer_id(alice), await _me(alice)
    deal_id = await _register(alice, customer_id, "A-1", a)

    edited = await bob.put(
        f"{DEALS}/{deal_id}",
        json=deal_payload(customer_id, code="A-1", owner_user_id=a, name="Bob이 수정"),
    )

    assert edited.status_code == 200
    assert await _codes(alice, mine="true") == ["A-1"]
    assert await _codes(bob, mine="true") == []


async def test_another_user_changing_the_stage_does_not_take_ownership(
    client_for: ClientFor,
) -> None:
    alice, bob = await client_for("alice"), await client_for("bob")
    deal_id = await _register(alice, await _customer_id(alice), "A-1", await _me(alice))

    moved = await bob.post(f"{DEALS}/{deal_id}/stage", json={"stage": "introduction"})

    assert moved.status_code == 200
    assert await _codes(alice, mine="true", stage="introduction") == ["A-1"]
    assert await _codes(bob, mine="true") == []


async def test_responses_expose_the_owner_but_never_the_registrant(client_for: ClientFor) -> None:
    alice = await client_for("alice")
    customer_id, a = await _customer_id(alice), await _me(alice)
    created = await alice.post(DEALS, json=deal_payload(customer_id, code="A-1", owner_user_id=a))
    deal_id = created.json()["id"]
    payload = deal_payload(customer_id, code="A-1", owner_user_id=a)

    bodies = [
        created.json(),
        (await alice.get(f"{DEALS}/{deal_id}")).json(),
        (await alice.get(f"{DEALS}/by-code/A-1")).json(),
        (await alice.get(DEALS, params={"mine": "true"})).json()["items"][0],
        (await alice.put(f"{DEALS}/{deal_id}", json=payload)).json(),
    ]

    for body in bodies:
        assert body["owner"]["id"] == a
        assert "registered_by_user_id" not in body
        assert "owner_user_id" not in body


async def test_mine_must_be_a_boolean(client_for: ClientFor) -> None:
    alice = await client_for("alice")

    for path in (DEALS, PIPELINE):
        response = await alice.get(path, params={"mine": "maybe"})

        assert response.status_code == 422, path
        assert response.json()["type"].endswith("request-validation")


async def test_pipeline_does_not_accept_an_owner_user_id_parameter(client_for: ClientFor) -> None:
    alice = await client_for("alice")

    response = await alice.get(PIPELINE, params={"owner_user_id": await _me(alice)})

    assert response.status_code == 422
    assert response.json()["type"].endswith("request-validation")


async def test_mine_requires_login(anonymous_client: AsyncClient) -> None:
    for path in (DEALS, PIPELINE):
        response = await anonymous_client.get(path, params={"mine": "true"})

        assert response.status_code == 401, path
        assert response.json()["type"].endswith("unauthenticated")


async def test_pipeline_mine_counts_only_my_deals(client_for: ClientFor) -> None:
    alice, bob = await client_for("alice"), await client_for("bob")
    customer_id = await _customer_id(alice)
    a, b = await _me(alice), await _me(bob)
    await _register(alice, customer_id, "A-1", a, revenue_amount="10")
    kept = await _register(alice, customer_id, "A-2", a, revenue_amount="5")
    await _register(bob, customer_id, "B-1", b, revenue_amount="1000")
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
    await _register(alice, await _customer_id(alice), "A-1", await _me(alice))

    stages = (await carol.get(PIPELINE, params={"mine": "true"})).json()["stages"]

    assert len(stages) == 8
    assert all(s["deal_count"] == 0 and s["totals"] == [] for s in stages)


def test_openapi_documents_owner_filter_for_deals_and_only_mine_for_the_pipeline() -> None:
    schema = create_app(settings=make_settings(), use_cases=FakeUseCases()).openapi()

    deal_params = {p["name"]: p for p in schema["paths"][DEALS]["get"]["parameters"]}
    pipeline_params = {p["name"]: p for p in schema["paths"][PIPELINE]["get"]["parameters"]}
    for params in (deal_params, pipeline_params):
        assert params["mine"]["schema"]["type"] == "boolean"
        assert params["mine"]["schema"]["default"] is False
        assert not params["mine"].get("required")
    assert "owner_user_id" in deal_params
    assert "owner" not in deal_params  # 텍스트 담당자 필터는 없어졌다
    assert "owner_user_id" not in pipeline_params
    components = schema["components"]["schemas"]
    assert "owner" in components["DealResponse"]["properties"]
    assert "owner_user_id" not in components["DealResponse"]["properties"]
    assert "registered_by_user_id" not in components["DealResponse"]["properties"]
    assert "owner_user_id" in components["DealRequest"]["properties"]
    assert "owner" not in components["DealRequest"]["properties"]
