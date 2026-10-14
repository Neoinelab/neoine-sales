"""현재 head 스키마(사용자 FK 이후)에 원시 SQL로 행을 넣는 도우미.

과거 리비전 스키마용 도우미는 tests.integration.test_migrations._insert_deal /
tests.integration.test_auth_migration._insert_user 에 그대로 남아 있다(문자열 컬럼 시절).
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INSERT_USER = (
    "insert into users (id, login_id, role, display_name, created_by_user_id, created_at,"
    " updated_at, deleted_at, delete_reason) values (:id, :login_id, :role, :display_name,"
    " :created_by_user_id, now(), now(), :deleted_at, :delete_reason)"
)
INSERT_DEAL = (
    "insert into deals (id, code, name, owner_user_id, registered_by_user_id, vendor, solution,"
    " revenue_amount, revenue_currency, revenue_date, customer_id, created_at, updated_at)"
    " values (:id, :code, 'n', :owner_user_id, :registered_by_user_id, 'v', 's', :amount, 'KRW',"
    " current_date, :customer_id, now(), now())"
)
INSERT_ACTION = (
    "insert into deal_actions (id, deal_id, action_type, action, memo, next_action, due_date,"
    " acted_at, actor_user_id, created_at, updated_at) values (:id, :deal_id, 'meeting', 'a', '',"
    " 'n', current_date, now(), :actor_user_id, now(), now())"
)
INSERT_CHANGE = (
    "insert into deal_stage_changes (id, deal_id, from_stage, to_stage, reason,"
    " changed_by_user_id, changed_at) values (:id, :deal_id, 'prospecting', 'introduction',"
    " null, :changed_by_user_id, now())"
)


async def insert_user(session: AsyncSession, login_id: str = "kim", **overrides: object) -> UUID:
    """재직 사용자 한 행(스스로 등록한 행). 퇴사 행은 deleted_at/delete_reason을 덮어쓴다."""
    new_id = uuid4()
    values: dict[str, object] = {
        "id": new_id,
        "login_id": login_id,
        "role": "sales",
        "display_name": None,
        "created_by_user_id": new_id,
        "deleted_at": None,
        "delete_reason": None,
    }
    values.update(overrides)
    await session.execute(text(INSERT_USER), values)
    return UUID(str(values["id"]))


async def insert_resigned_user(session: AsyncSession, login_id: str = "gone") -> UUID:
    return await insert_user(
        session,
        login_id,
        deleted_at=datetime(2026, 1, 2, tzinfo=UTC),
        delete_reason="resigned",
    )


async def insert_deal(
    session: AsyncSession, customer_id: str, owner_user_id: UUID | None = None, **overrides: object
) -> UUID:
    """담당자 행이 없으면 새로 만든다. 새 Deal의 id를 돌려준다."""
    owner = owner_user_id or await insert_user(session, f"o{uuid4().hex[:10]}")
    values: dict[str, object] = {
        "id": uuid4(),
        "code": "D-1",
        "customer_id": customer_id,
        "amount": 100,
        "owner_user_id": owner,
        "registered_by_user_id": None,
    }
    values.update(overrides)
    await session.execute(text(INSERT_DEAL), values)
    return UUID(str(values["id"]))
