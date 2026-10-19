"""head 스키마 카탈로그 점검(AC1·2, T1~T5): CASCADE·FK·인덱스 누락, 문자열 사용자 참조 차단.

실제 마이그레이션 head를 임시 DB에 적용한 뒤 카탈로그를 검사한다. 허용 예외는 하나뿐이다: Deal 소속
데이터(파트너 링크·BANT 선택·이력·활동)가 deals를 가리키는 FK는 CASCADE다(아래 시험이 집합을 고정).
users.login_id의 유일성은 응용 로직이 지키므로 그 컬럼의 유니크 여부는 단언하지 않는다.
점검 함수 자체의 검증은 test_schema_checker.py.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from app.infra.db import models  # noqa: F401 - 메타데이터 등록
from app.infra.db.base import Base
from tests.support.schema_integrity import check_schema, foreign_keys, user_foreign_keys
from tests.support.user_links import EXPECTED_USER_FKS

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

USER_FK_NAMES = {
    ("deals", "owner_user_id"): "fk_deals_owner_user_id_users",
    ("deal_actions", "actor_user_id"): "fk_deal_actions_actor_user_id_users",
    ("auth_sessions", "user_id"): "fk_auth_sessions_user_id_users",
    ("deal_history", "changed_by_user_id"): "fk_deal_history_changed_by_user_id_users",
    ("users", "created_by_user_id"): "fk_users_created_by_user_id_users",
    ("directory_settings", "updated_by_user_id"): "fk_directory_settings_updated_by_user_id_users",
    ("bant_labels", "created_by_user_id"): "fk_bant_labels_created_by_user_id_users",
    ("storage_settings", "updated_by_user_id"): "fk_storage_settings_updated_by_user_id_users",
    ("deal_attachments", "uploaded_by_user_id"): "fk_deal_attachments_uploaded_by_user_id_users",
    ("alert_settings", "updated_by_user_id"): "fk_alert_settings_updated_by_user_id_users",
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
        ("deal_history", "changed_by_user_id"),
        ("users", "created_by_user_id"),
    } <= not_null
    assert (
        "deals",
        "registered_by_user_id",
    ) not in by_column  # 등록자 컬럼은 없다(이력이 대신한다)
    assert ("directory_settings", "updated_by_user_id") not in not_null  # 최초 설정
    assert ("storage_settings", "updated_by_user_id") not in not_null  # 최초 설정(P2b)
    assert ("deal_attachments", "uploaded_by_user_id") in not_null
    assert ("alert_settings", "updated_by_user_id") in not_null  # 최초 설정 경로가 없다(P3)


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


async def test_only_deal_owned_data_and_vendor_solutions_cascade(session: AsyncSession) -> None:
    """CASCADE 예외 둘: Deal 소속 데이터는 Deal을, Solution은 소속 Vendor를 지우면 함께 지워진다."""
    cascades = {
        fk.table + "." + fk.column for fk in await foreign_keys(session) if fk.on_delete == "c"
    }

    assert cascades == {
        "deal_partners.deal_code",
        "deal_bant_labels.deal_code",
        "deal_history.deal_code",
        "deal_actions.deal_code",
        "deal_attachments.deal_code",  # P2b: 첨부 메타데이터도 Deal 소속이다
        "solutions.vendor_id",  # Vendor Aggregate: Vendor 삭제는 소속 Solution과 함께(D10)
    }
    assert all(
        fk.ref_table == ("vendors" if fk.table == "solutions" else "deals")
        for fk in await foreign_keys(session)
        if fk.on_delete == "c"
    )
