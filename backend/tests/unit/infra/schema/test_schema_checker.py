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
    """ON DELETE CASCADE 외래 키는 위반으로 잡는다."""
    # when: CASCADE 외래 키가 있는 스키마를 점검한다
    #   (전제: CASCADE 외래 키와 인덱스가 있는 자식 테이블)
    rules = await _violations(
        session,
        "create table zz_meta_child (id bigint primary key, ref_id bigint"
        " references zz_meta_users(id) on delete cascade)",
        "create index on zz_meta_child (ref_id)",
    )

    # then: RESTRICT가 아니라는 위반 하나다
    assert rules == ["fk_not_restrict"]


async def test_checker_flags_a_deferrable_foreign_key(session: AsyncSession) -> None:
    """DEFERRABLE 외래 키는 위반으로 잡는다."""
    # when: DEFERRABLE 외래 키가 있는 스키마를 점검한다
    #   (전제: DEFERRABLE 외래 키와 인덱스가 있는 자식 테이블)
    rules = await _violations(
        session,
        "create table zz_meta_child (id bigint primary key, ref_id bigint"
        " references zz_meta_users(id) on delete restrict deferrable initially deferred)",
        "create index on zz_meta_child (ref_id)",
    )

    # then: 지연 가능 위반 하나다
    assert rules == ["fk_deferrable"]


async def test_checker_flags_a_foreign_key_column_without_a_leading_index(
    session: AsyncSession,
) -> None:
    """외래 키 컬럼이 선두인 인덱스가 없으면 위반으로 잡는다."""
    # when: 선두 인덱스 없는 외래 키 컬럼이 있는 스키마를 점검한다
    #   (전제: 인덱스가 없는 외래 키 컬럼을 가진 자식 테이블)
    rules = await _violations(
        session,
        "create table zz_meta_child (id bigint primary key, ref_id bigint"
        " references zz_meta_users(id) on delete restrict)",
    )

    # then: 선두 인덱스 없음 위반 하나다
    assert rules == ["fk_column_without_leading_index"]


async def test_checker_accepts_a_composite_index_that_starts_with_the_foreign_key_column(
    session: AsyncSession,
) -> None:
    """외래 키 컬럼으로 시작하는 복합 인덱스는 위반이 아니다."""
    # when: 외래 키로 시작하는 복합 인덱스가 있는 스키마를 점검한다
    #   (전제: 외래 키 컬럼이 선두인 복합 인덱스를 가진 자식 테이블)
    rules = await _violations(
        session,
        "create table zz_meta_child (id bigint primary key, ref_id bigint"
        " references zz_meta_users(id) on delete restrict, at timestamptz)",
        "create index on zz_meta_child (ref_id, at)",
    )

    # then: 위반이 없다
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
    """사용자 참조 컬럼이 users를 가리키는 bigint 외래 키가 아니면 위반으로 잡는다."""
    # when: bigint 외래 키가 아닌 사용자 참조가 있는 스키마를 점검한다
    #   (전제: users 외래 키가 아닌 사용자 참조 컬럼을 가진 자식 테이블)
    rules = await _violations(
        session, f"create table zz_meta_child (id bigint primary key, {column_sql})"
    )

    # then: 사용자 참조 위반 하나다
    assert rules == ["user_reference_not_a_bigint_fk_to_users"]


async def test_checker_flags_a_bigint_user_reference_to_a_table_other_than_users(
    session: AsyncSession,
) -> None:
    """사용자 참조 bigint 컬럼이 users 아닌 테이블을 가리키면 위반으로 잡는다."""
    # when: users 아닌 테이블을 가리키는 사용자 참조가 있는 스키마를 점검한다
    #   (전제: users가 아닌 테이블을 참조하는 owner_user_id를 가진 자식 테이블)
    rules = await _violations(
        session,
        "create table zz_meta_other (id bigint primary key)",
        "create table zz_meta_child (id bigint primary key, owner_user_id bigint"
        " references zz_meta_other(id) on delete restrict)",
        "create index on zz_meta_child (owner_user_id)",
    )

    # then: 사용자 참조 위반 하나다
    assert rules == ["user_reference_not_a_bigint_fk_to_users"]


async def test_checker_flags_deleted_at_on_a_table_other_than_users(session: AsyncSession) -> None:
    """users 아닌 테이블의 deleted_at 컬럼은 위반으로 잡는다."""
    # when: users 아닌 테이블에 deleted_at이 있는 스키마를 점검한다
    #   (전제: deleted_at이 있는 자식 테이블)
    rules = await _violations(
        session, "create table zz_meta_child (id bigint primary key, deleted_at timestamptz)"
    )

    # then: deleted_at 위반 하나다
    assert rules == ["deleted_at_outside_users"]


async def test_checker_passes_a_clean_child_table(session: AsyncSession) -> None:
    """규칙을 지킨 자식 테이블은 위반이 없다."""
    # when: 규칙을 지킨 자식 테이블의 스키마를 점검한다
    #   (전제: users를 RESTRICT로 참조하고 인덱스도 있는 자식 테이블)
    rules = await _violations(
        session,
        "create table zz_meta_child (id bigint primary key, owner_user_id bigint not null"
        " references users(id) on delete restrict)",
        "create index on zz_meta_child (owner_user_id)",
    )

    # then: 위반이 없다
    assert rules == []
