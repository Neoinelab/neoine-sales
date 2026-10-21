"""스키마 점검 함수(`tests.support.schema_integrity.check_schema`) 자체의 단위 테스트.

일부러 규칙을 어긴 임시 테이블을 만들어 위반이 잡히는지 확인한다(세션은 테스트마다 롤백된다).
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from tests.support.schema_integrity import check_schema

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

PARENT = "create table zz_meta_users (id bigint primary key)"


async def _violations(session: AsyncSession, *statements: str) -> list[str]:
    await session.execute(text(PARENT))
    for statement in statements:
        await session.execute(text(statement))
    found = await check_schema(session, only_tables={"zz_meta_child", "zz_meta_users"})
    return [v.rule for v in found if v.table == "zz_meta_child"]


async def test_checker_flags_a_cascade_foreign_key(session: AsyncSession) -> None:
    rules = await _violations(
        session,
        "create table zz_meta_child (id bigint primary key, ref_id bigint"
        " references zz_meta_users(id) on delete cascade)",
        "create index on zz_meta_child (ref_id)",
    )

    assert rules == ["fk_not_restrict"]


async def test_checker_flags_a_deferrable_foreign_key(session: AsyncSession) -> None:
    rules = await _violations(
        session,
        "create table zz_meta_child (id bigint primary key, ref_id bigint"
        " references zz_meta_users(id) on delete restrict deferrable initially deferred)",
        "create index on zz_meta_child (ref_id)",
    )

    assert rules == ["fk_deferrable"]


async def test_checker_flags_a_foreign_key_column_without_a_leading_index(
    session: AsyncSession,
) -> None:
    rules = await _violations(
        session,
        "create table zz_meta_child (id bigint primary key, ref_id bigint"
        " references zz_meta_users(id) on delete restrict)",
    )

    assert rules == ["fk_column_without_leading_index"]


async def test_checker_accepts_a_composite_index_that_starts_with_the_foreign_key_column(
    session: AsyncSession,
) -> None:
    rules = await _violations(
        session,
        "create table zz_meta_child (id bigint primary key, ref_id bigint"
        " references zz_meta_users(id) on delete restrict, at timestamptz)",
        "create index on zz_meta_child (ref_id, at)",
    )

    assert rules == []


@pytest.mark.parametrize(
    "column_sql",
    [
        "created_by varchar(200)",
        "updated_by text",
        "changed_by_name varchar(200)",
        "owner varchar(100)",
        "actor varchar(100)",
        "subject varchar(200)",
        "registered_by_user_id bigint",
    ],
)
async def test_checker_flags_a_user_reference_that_is_not_a_bigint_foreign_key_to_users(
    session: AsyncSession, column_sql: str
) -> None:
    rules = await _violations(
        session, f"create table zz_meta_child (id bigint primary key, {column_sql})"
    )

    assert rules == ["user_reference_not_a_bigint_fk_to_users"]


async def test_checker_flags_a_bigint_user_reference_to_a_table_other_than_users(
    session: AsyncSession,
) -> None:
    rules = await _violations(
        session,
        "create table zz_meta_other (id bigint primary key)",
        "create table zz_meta_child (id bigint primary key, owner_user_id bigint"
        " references zz_meta_other(id) on delete restrict)",
        "create index on zz_meta_child (owner_user_id)",
    )

    assert rules == ["user_reference_not_a_bigint_fk_to_users"]


async def test_checker_flags_deleted_at_on_a_table_other_than_users(session: AsyncSession) -> None:
    rules = await _violations(
        session, "create table zz_meta_child (id bigint primary key, deleted_at timestamptz)"
    )

    assert rules == ["deleted_at_outside_users"]


async def test_checker_passes_a_clean_child_table(session: AsyncSession) -> None:
    rules = await _violations(
        session,
        "create table zz_meta_child (id bigint primary key, owner_user_id bigint not null"
        " references users(id) on delete restrict)",
        "create index on zz_meta_child (owner_user_id)",
    )

    assert rules == []
