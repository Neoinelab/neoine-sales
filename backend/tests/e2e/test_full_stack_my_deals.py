"""내 딜(mine) 전 구간 통합 테스트: 두 사용자가 실제 PostgreSQL에서 서로의 딜을 구분한다."""

from typing import TYPE_CHECKING

import pytest

from tests.e2e.payloads import customer_payload, deal_payload

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from httpx import AsyncClient

    ClientFor = Callable[[str], Awaitable[AsyncClient]]

CUSTOMERS = "/api/v1/customers"
DEALS = "/api/v1/deals"


@pytest.mark.integration
async def test_my_deals_filter_runs_in_the_database(stack_for: ClientFor) -> None:
    alice, bob = await stack_for("alice"), await stack_for("bob")
    a = (await alice.get("/api/v1/auth/me")).json()["user_id"]
    b = (await bob.get("/api/v1/auth/me")).json()["user_id"]
    customer = (await alice.post(CUSTOMERS, json=customer_payload())).json()
    for client, code, owner in ((alice, "A-1", a), (bob, "B-1", b), (alice, "A-2", a)):
        payload = deal_payload(customer["id"], code=code, owner_user_id=owner)
        assert (await client.post(DEALS, json=payload)).status_code == 201
    moved = (await alice.get(DEALS, params={"keyword": "A-2"})).json()["items"][0]["id"]
    assert (
        await alice.post(f"{DEALS}/{moved}/stage", json={"stage": "lost", "reason": "x"})
    ).status_code == 200

    async def codes(client: AsyncClient, **params: str) -> list[str]:
        response = await client.get(DEALS, params=params)
        assert response.status_code == 200, response.text
        return [item["code"] for item in response.json()["items"]]

    async def prospecting(client: AsyncClient, **params: str) -> int:
        response = await client.get(f"{DEALS}/pipeline", params=params)
        assert response.status_code == 200, response.text
        return int(response.json()["stages"][0]["deal_count"])

    assert await codes(alice, mine="true") == ["A-1", "A-2"]
    assert await codes(bob, mine="true") == ["B-1"]
    assert await codes(alice, mine="true", stage="lost") == ["A-2"]
    assert await codes(alice) == ["A-1", "B-1", "A-2"]
    assert await prospecting(alice, mine="true") == 1
    assert await prospecting(bob, mine="true") == 1
    assert await prospecting(alice) == 2
    edited = await bob.put(
        f"{DEALS}/{moved}",
        json=deal_payload(customer["id"], code="A-2", owner_user_id=a, name="Bob이 수정"),
    )
    assert edited.status_code == 200
    assert await codes(alice, mine="true") == ["A-1", "A-2"]
    assert await codes(bob, mine="true") == ["B-1"]
