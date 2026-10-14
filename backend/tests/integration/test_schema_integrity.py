"""스키마 점검 테스트(AC1·2, T1~T5): CASCADE/FK 누락/인덱스 누락/문자열 사용자 참조를 영구 차단한다.

실제 마이그레이션 head를 임시 DB에 적용한 뒤 카탈로그를 검사한다. 허용 예외 목록은 없다.
users.login_id의 유일성은 응용 로직이 지키므로 그 컬럼의 유니크 여부는 단언하지 않는다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from app.infra.db import models  # noqa: F401 - 메타데이터 등록
from app.infra.db.base import Base
from tests.support.schema_integrity import check_schema, user_foreign_keys
from tests.support.user_links import EXPECTED_USER_FKS

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

USER_FK_NAMES = {
    ("deals", "owner_user_id"): "fk_deals_owner_user_id_users",
    ("deals", "registered_by_user_id"): "fk_deals_registered_by_user_id_users",
    ("deal_actions", "actor_user_id"): "fk_deal_actions_actor_user_id_users",
    ("auth_sessions", "user_id"): "fk_auth_sessions_user_id_users",
    ("deal_stage_changes", "changed_by_user_id"): "fk_deal_stage_changes_changed_by_user_id_users",
    ("users", "created_by_user_id"): "fk_users_created_by_user_id_users",
    ("directory_settings", "updated_by_user_id"): "fk_directory_settings_updated_by_user_id_users",
}
OLD_STRING_COLUMNS = {
    ("deals", "owner"),
    ("deal_actions", "actor"),
    ("auth_sessions", "subject"),
    ("deal_stage_changes", "changed_by_subject"),
    ("deal_stage_changes", "changed_by_name"),
    ("users", "created_by"),
    ("directory_settings", "updated_by"),
}


async def test_head_schema_has_no_integrity_violations(session: AsyncSession) -> None:
    assert await check_schema(session) == []


async def test_every_foreign_key_to_users_is_exactly_the_expected_set(
    session: AsyncSession,
) -> None:
    """has_links가 수집하는 FK 집합(= 기대 집합)과 실제 카탈로그가 같다."""
    assert await user_foreign_keys(session) == set(EXPECTED_USER_FKS)


async def test_orm_metadata_lists_the_same_user_foreign_keys_as_the_database(
    session: AsyncSession,
) -> None:
    from_metadata = {
        (table.name, fk.parent.name)
        for table in Base.metadata.tables.values()
        for fk in table.foreign_keys
        if fk.column.table.name == "users"
    }

    assert from_metadata == await user_foreign_keys(session)


async def test_user_foreign_keys_use_the_planned_names_and_restrict(session: AsyncSession) -> None:
    rows = (
        await session.execute(
            text(
                "select c.conrelid::regclass::text, a.attname, c.conname, c.confdeltype::text,"
                " c.condeferrable from pg_constraint c join pg_attribute a"
                " on a.attrelid = c.conrelid and a.attnum = c.conkey[1]"
                " where c.contype = 'f' and c.confrelid = 'users'::regclass"
            )
        )
    ).all()

    found = {(r[0], r[1]): (r[2], r[3].strip(), r[4]) for r in rows}

    assert found == {key: (name, "r", False) for key, name in USER_FK_NAMES.items()}


async def test_user_reference_columns_are_uuid_and_the_old_string_columns_are_gone(
    session: AsyncSession,
) -> None:
    rows = (
        await session.execute(
            text(
                "select table_name, column_name, udt_name, is_nullable"
                " from information_schema.columns where table_schema = 'public'"
            )
        )
    ).all()
    by_column = {(r[0], r[1]): (r[2], r[3]) for r in rows}

    assert not (OLD_STRING_COLUMNS & set(by_column))
    for key in USER_FK_NAMES:
        assert by_column[key][0] == "uuid", key
    not_null = {key for key, (_, nullable) in by_column.items() if nullable == "NO"}
    assert {
        ("deals", "owner_user_id"),
        ("deal_actions", "actor_user_id"),
        ("auth_sessions", "user_id"),
        ("deal_stage_changes", "changed_by_user_id"),
        ("users", "created_by_user_id"),
    } <= not_null
    assert ("deals", "registered_by_user_id") not in not_null  # 과거 딜
    assert ("directory_settings", "updated_by_user_id") not in not_null  # 최초 설정


async def test_deleted_at_exists_only_on_users_with_its_two_check_constraints(
    session: AsyncSession,
) -> None:
    tables = {
        r[0]
        for r in (
            await session.execute(
                text(
                    "select table_name from information_schema.columns"
                    " where table_schema = 'public' and column_name = 'deleted_at'"
                )
            )
        ).all()
    }
    checks = {
        r[0]
        for r in (
            await session.execute(
                text("select conname from pg_constraint where conrelid = 'users'::regclass")
            )
        ).all()
    }

    assert tables == {"users"}
    assert {"ck_users_delete_reason_valid", "ck_users_deleted_pair"} <= checks
    reason = (
        await session.execute(
            text(
                "select pg_get_constraintdef(oid) from pg_constraint"
                " where conname = 'ck_users_delete_reason_valid'"
            )
        )
    ).scalar_one()
    assert "resigned" in reason


async def test_every_foreign_key_column_leads_an_index(session: AsyncSession) -> None:
    violations = [v for v in await check_schema(session) if v.rule.endswith("leading_index")]

    assert violations == []


# --- 점검 함수 자체의 검증: 일부러 규칙을 어긴 임시 테이블을 만들어 위반이 잡히는지 확인한다 ---

PARENT = "create table zz_meta_users (id uuid primary key)"


async def _violations(session: AsyncSession, *statements: str) -> list[str]:
    await session.execute(text(PARENT))
    for statement in statements:
        await session.execute(text(statement))
    found = await check_schema(session, only_tables={"zz_meta_child", "zz_meta_users"})
    return [v.rule for v in found if v.table == "zz_meta_child"]


async def test_checker_flags_a_cascade_foreign_key(session: AsyncSession) -> None:
    rules = await _violations(
        session,
        "create table zz_meta_child (id uuid primary key, ref_id uuid"
        " references zz_meta_users(id) on delete cascade)",
        "create index on zz_meta_child (ref_id)",
    )

    assert rules == ["fk_not_restrict"]


async def test_checker_flags_a_deferrable_foreign_key(session: AsyncSession) -> None:
    rules = await _violations(
        session,
        "create table zz_meta_child (id uuid primary key, ref_id uuid"
        " references zz_meta_users(id) on delete restrict deferrable initially deferred)",
        "create index on zz_meta_child (ref_id)",
    )

    assert rules == ["fk_deferrable"]


async def test_checker_flags_a_foreign_key_column_without_a_leading_index(
    session: AsyncSession,
) -> None:
    rules = await _violations(
        session,
        "create table zz_meta_child (id uuid primary key, ref_id uuid"
        " references zz_meta_users(id) on delete restrict)",
    )

    assert rules == ["fk_column_without_leading_index"]


async def test_checker_accepts_a_composite_index_that_starts_with_the_foreign_key_column(
    session: AsyncSession,
) -> None:
    rules = await _violations(
        session,
        "create table zz_meta_child (id uuid primary key, ref_id uuid"
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
        "registered_by_user_id uuid",
    ],
)
async def test_checker_flags_a_user_reference_that_is_not_a_uuid_foreign_key_to_users(
    session: AsyncSession, column_sql: str
) -> None:
    rules = await _violations(
        session, f"create table zz_meta_child (id uuid primary key, {column_sql})"
    )

    assert rules == ["user_reference_not_a_uuid_fk_to_users"]


async def test_checker_flags_a_uuid_user_reference_to_a_table_other_than_users(
    session: AsyncSession,
) -> None:
    rules = await _violations(
        session,
        "create table zz_meta_other (id uuid primary key)",
        "create table zz_meta_child (id uuid primary key, owner_user_id uuid"
        " references zz_meta_other(id) on delete restrict)",
        "create index on zz_meta_child (owner_user_id)",
    )

    assert rules == ["user_reference_not_a_uuid_fk_to_users"]


async def test_checker_flags_deleted_at_on_a_table_other_than_users(session: AsyncSession) -> None:
    rules = await _violations(
        session, "create table zz_meta_child (id uuid primary key, deleted_at timestamptz)"
    )

    assert rules == ["deleted_at_outside_users"]


async def test_checker_passes_a_clean_child_table(session: AsyncSession) -> None:
    rules = await _violations(
        session,
        "create table zz_meta_child (id uuid primary key, owner_user_id uuid not null"
        " references users(id) on delete restrict)",
        "create index on zz_meta_child (owner_user_id)",
    )

    assert rules == []
