"""deleted_at 제거 마이그레이션 테스트의 준비 도우미(이전 head 스키마에 행을 넣는다)."""

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from tests.integration.test_auth_migration import _insert_user
from tests.integration.test_migrations import _insert_customer, _insert_deal

if TYPE_CHECKING:
    from collections.abc import Collection

    from sqlalchemy.engine import URL

PREVIOUS_HEAD = "e3a9c41b7d52"
TABLES = ("customers", "partners", "deals", "deal_actions", "users")
CODE = "KEEP-1"


async def seed_rows(session: AsyncSession, soft_deleted: Collection[str] = ()) -> None:
    """5개 테이블에 행을 1건씩 넣고, soft_deleted에 든 테이블의 행에만 deleted_at을 채운다."""
    customer_id = await _insert_customer(session)
    partner_id = uuid4()
    deal_id, action_id = uuid4(), uuid4()
    await session.execute(
        text(
            "insert into partners (id, company_name, contact_name, created_at, updated_at)"
            " values (:id, 'p', 'c', now(), now())"
        ),
        {"id": partner_id},
    )
    await _insert_deal(session, customer_id, id=deal_id, code=CODE, partner_id=partner_id)
    await session.execute(
        text(
            "insert into deal_actions (id, deal_id, action_type, action, memo, next_action,"
            " due_date, acted_at, actor, created_at, updated_at) values (:id, :deal_id,"
            " 'meeting', 'a', '', 'n', current_date, now(), '박영업', now(), now())"
        ),
        {"id": action_id, "deal_id": deal_id},
    )
    await _insert_user(session, "kim")
    for table in soft_deleted:
        await session.execute(text(f"update {table} set deleted_at = now()"))  # noqa: S608


async def run_sql(url: URL, statement: str) -> list[tuple[object, ...]]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return [tuple(row) for row in (await connection.execute(text(statement))).all()]
    finally:
        await engine.dispose()


async def seed(url: URL, soft_deleted: Collection[str] = ()) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await seed_rows(AsyncSession(bind=connection), soft_deleted)
    finally:
        await engine.dispose()


async def deleted_at_tables(url: URL) -> set[str]:
    rows = await run_sql(
        url,
        "select table_name from information_schema.columns where column_name = 'deleted_at'"
        " and table_schema = 'public'",
    )
    return {str(r[0]) for r in rows} & set(TABLES)


async def row_counts(url: URL) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLES:
        rows = await run_sql(url, f"select count(*) from {table}")  # noqa: S608
        counts[table] = int(str(rows[0][0]))
    return counts


async def user_index_names(url: URL) -> set[str]:
    rows = await run_sql(
        url, "select indexname from pg_indexes where indexname like 'uq_users_login_id%'"
    )
    return {str(r[0]) for r in rows}
