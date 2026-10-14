"""Deal 이력 전 구간(PostgreSQL): 기존(NULL 계획) 행 조회, 삭제 정책, FK 방어(AC8, 10~12)."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.e2e.payloads import action_payload, customer_payload, deal_payload
from tests.support.user_ids import ACTOR_ID

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

DEALS = "/api/v1/deals"
ACTIONS = "/api/v1/deal-actions"

INSERT_LEGACY = (  # 계획 필드(next_action·due_date)가 NULL인 기존 행. 활동자는 users 행을 가리킨다
    "insert into deal_actions (id, deal_id, action_type, action, memo, acted_at, actor_user_id,"
    " created_at, updated_at) values (:id, :deal_id, 'call', '기존 통화', '기존 메모', now(),"
    " :actor_user_id, now(), now())"
)


def _legacy_params(action_id: object, deal_id: str) -> dict[str, object]:
    return {"id": action_id, "deal_id": deal_id, "actor_user_id": ACTOR_ID}


async def _deal(stack: AsyncClient) -> str:
    customer = (await stack.post("/api/v1/customers", json=customer_payload())).json()
    return str((await stack.post(DEALS, json=deal_payload(customer["id"]))).json()["id"])


async def test_legacy_rows_with_null_plan_fields_are_listed_as_null(
    stack: AsyncClient, test_database_url: URL
) -> None:
    deal_id = await _deal(stack)
    legacy_id = uuid4()
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(INSERT_LEGACY), _legacy_params(legacy_id, deal_id))
    finally:
        await engine.dispose()

    listed = await stack.get(f"{DEALS}/{deal_id}/actions")
    single = await stack.get(f"{ACTIONS}/{legacy_id}")
    global_search = await stack.get(ACTIONS, params={"sort": "due_date_asc"})

    assert listed.status_code == single.status_code == global_search.status_code == 200
    item = listed.json()["items"][0]
    assert (item["action"], item["memo"]) == ("기존 통화", "기존 메모")
    assert item["next_action"] is None
    assert item["due_date"] is None
    assert single.json()["due_date"] is None
    assert [i["id"] for i in global_search.json()["items"]] == [str(legacy_id)]


async def test_legacy_row_can_only_be_updated_with_the_plan_fields(
    stack: AsyncClient, test_database_url: URL
) -> None:
    deal_id = await _deal(stack)
    legacy_id = uuid4()
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(INSERT_LEGACY), _legacy_params(legacy_id, deal_id))
    finally:
        await engine.dispose()
    payload = action_payload()
    del payload["next_action"]

    rejected = await stack.put(f"{ACTIONS}/{legacy_id}", json=payload)
    accepted = await stack.put(f"{ACTIONS}/{legacy_id}", json=action_payload())

    assert rejected.status_code == 422
    assert accepted.status_code == 200
    assert accepted.json()["due_date"] == "2026-03-10"


async def test_action_delete_and_deal_delete_policy_in_the_database(stack: AsyncClient) -> None:
    deal_id = await _deal(stack)
    created = (await stack.post(f"{DEALS}/{deal_id}/actions", json=action_payload())).json()

    blocked = await stack.delete(f"{DEALS}/{deal_id}")
    assert blocked.status_code == 409
    assert blocked.json()["type"].endswith("invalid-state")
    assert (await stack.delete(f"{ACTIONS}/{created['id']}")).status_code == 204
    assert (await stack.get(f"{ACTIONS}/{created['id']}")).status_code == 404

    assert (await stack.delete(f"{DEALS}/{deal_id}")).status_code == 204
    assert (await stack.get(f"{DEALS}/{deal_id}")).status_code == 404
    customer_id = (await stack.get("/api/v1/customers")).json()["items"][0]["id"]
    again = await stack.post(DEALS, json=deal_payload(customer_id))
    assert again.status_code == 201  # 물리 삭제로 같은 코드를 다시 쓸 수 있다
