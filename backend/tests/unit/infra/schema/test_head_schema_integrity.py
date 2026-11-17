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
    ("directory_settings", "updated_by_user_id"): "fk_directory_settings_updated_by_user_id_users",
    ("bant_labels", "created_by_user_id"): "fk_bant_labels_created_by_user_id_users",
    ("action_types", "created_by_user_id"): "fk_action_types_created_by_user_id_users",
    ("storage_settings", "updated_by_user_id"): "fk_storage_settings_updated_by_user_id_users",
    ("deal_attachments", "uploaded_by_user_id"): "fk_deal_attachments_uploaded_by_user_id_users",
    ("alert_settings", "updated_by_user_id"): "fk_alert_settings_updated_by_user_id_users",
    ("forecast_snapshot_cells", "owner_user_id"): "fk_forecast_snapshot_cells_owner_user_id_users",
    ("reports", "owner_user_id"): "fk_reports_owner_user_id_users",
    ("reports", "updated_by_user_id"): "fk_reports_updated_by_user_id_users",
    ("partner_meetings", "created_by_user_id"): "fk_partner_meetings_created_by_user_id_users",
    ("license_contracts", "created_by_user_id"): "fk_license_contracts_created_by_user_id_users",
    ("deal_comments", "author_user_id"): "fk_deal_comments_author_user_id_users",
    ("license_contracts", "updated_by_user_id"): "fk_license_contracts_updated_by_user_id_users",
    (
        "license_contract_attachments",
        "uploaded_by_user_id",
    ): "fk_license_contract_attachments_uploaded_by_user_id_users",
}
# 대체 로그인용 비밀번호 해시는 사용자 삭제 때 함께 지워지므로(연결 아님) 유일하게 CASCADE다.
CASCADE_USER_FK_NAMES = {
    ("user_password_hashes", "user_id"): "fk_user_password_hashes_user_id_users",
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
    """head 스키마 점검(RESTRICT·DEFERRABLE·선행 인덱스·사용자 참조·deleted_at) 위반이 0건이다.

    테스트 코드: SC-024
    """
    # when: 스키마 점검 함수 check_schema를 실행한다 (전제: head를 적용한 임시 DB)
    violations = await check_schema(session)

    # then: 위반 목록이 비어 있다
    assert violations == []


async def test_every_foreign_key_to_users_is_exactly_the_expected_set(
    session: AsyncSession,
) -> None:
    """users를 가리키는 FK 집합이 사용자 연결 목록(EXPECTED_USER_FKS)과 같다.

    테스트 코드: SC-026
    """
    # when: users를 가리키는 FK의 (테이블, 컬럼) 집합을 읽는다 (전제: head를 적용한 임시 DB)
    found = await user_foreign_keys(session)

    # then: 사용자 연결 목록과 같고 users 자신을 가리키는 FK(등록자)는 없다
    assert found == set(EXPECTED_USER_FKS)
    assert ("users", "created_by_user_id") not in found


async def test_orm_metadata_lists_the_same_user_foreign_keys_as_the_database(
    session: AsyncSession,
) -> None:
    """ORM 메타데이터의 users FK 집합이 DB와 같다.

    테스트 코드: SC-027
    """
    # when: Base.metadata에서 users를 가리키는 FK의 (테이블, 컬럼) 집합을 모은다
    #   (전제: head를 적용한 임시 DB)
    from_metadata = {
        (table.name, fk.parent.name)
        for table in Base.metadata.tables.values()
        for fk in table.foreign_keys
        if fk.column.table.name == "users"
    }

    # then: DB에서 읽은 집합과 같다
    assert from_metadata == await user_foreign_keys(session)


async def test_user_foreign_keys_use_the_planned_names_and_restrict(session: AsyncSession) -> None:
    """users FK는 정해진 이름·RESTRICT·DEFERRABLE 아님이고 해시 테이블만 CASCADE다.

    테스트 코드: SC-028
    """
    # given: head를 적용한 임시 DB
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

    # when: users를 가리키는 FK의 이름·ON DELETE·DEFERRABLE을 읽는다
    found = {(r[0], r[1]): (r[2], r[3].strip(), r[4]) for r in rows}

    # then: RESTRICT 18개와 CASCADE 1개(해시)가 정해진 이름 그대로이고 그 밖의 FK는 없다
    expected = {key: (name, "r", False) for key, name in USER_FK_NAMES.items()}
    expected |= {key: (name, "c", False) for key, name in CASCADE_USER_FK_NAMES.items()}
    assert found == expected
    assert ("users", "created_by_user_id") not in found  # fk_users_created_by_user_id_users 없음


async def test_user_reference_columns_are_bigint_and_the_old_string_columns_are_gone(
    session: AsyncSession,
) -> None:
    """사용자 참조 컬럼은 bigint이고 예전 문자열·등록자 컬럼이 없으며 NOT NULL 여부가 정해진 대로다.

    테스트 코드: SC-029
    """
    # given: head를 적용한 임시 DB
    rows = (
        await session.execute(
            text(
                "select table_name, column_name, udt_name, is_nullable"
                " from information_schema.columns where table_schema = 'public'"
            )
        )
    ).all()
    # when: public 스키마 컬럼의 형식과 NULL 허용 여부를 읽는다
    by_column = {(r[0], r[1]): (r[2], r[3]) for r in rows}

    # then: 예전 문자열 컬럼이 없고, 사용자 FK 컬럼은 int8이며, NOT NULL 여부가 정해진 대로다
    assert not (OLD_STRING_COLUMNS & set(by_column))
    for key in USER_FK_NAMES:
        assert by_column[key][0] == "int8", key
    not_null = {key for key, (_, nullable) in by_column.items() if nullable == "NO"}
    assert {
        ("deals", "owner_user_id"),
        ("deal_actions", "actor_user_id"),
        ("auth_sessions", "user_id"),
        ("deal_history", "changed_by_user_id"),
    } <= not_null
    assert ("users", "created_by_user_id") not in by_column  # 등록자 컬럼 제거(SC-R21)
    assert (
        "deals",
        "registered_by_user_id",
    ) not in by_column  # 등록자 컬럼은 없다(이력이 대신한다)
    assert ("directory_settings", "updated_by_user_id") not in not_null  # 최초 설정
    assert ("storage_settings", "updated_by_user_id") not in not_null  # 최초 설정(P2b)
    assert ("deal_attachments", "uploaded_by_user_id") in not_null
    assert ("deal_comments", "author_user_id") in not_null  # Comment 작성자(SC-R17)
    assert ("alert_settings", "updated_by_user_id") in not_null  # 최초 설정 경로가 없다(P3)


async def test_deleted_at_exists_only_on_users_and_no_check_uses_it(
    session: AsyncSession,
) -> None:
    """deleted_at 컬럼은 users에만 있고 users에 deleted_at·delete_reason CHECK가 없다.

    테스트 코드: SC-030
    """
    # given: head를 적용한 임시 DB
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
    # when: deleted_at 컬럼을 가진 테이블과 users의 CHECK·컬럼을 읽는다
    checks = {
        r[0]
        for r in (
            await session.execute(
                text(
                    "select conname from pg_constraint"
                    " where conrelid = 'users'::regclass and contype = 'c'"
                )
            )
        ).all()
    }
    user_columns = {
        r[0]
        for r in (
            await session.execute(
                text(
                    "select column_name from information_schema.columns"
                    " where table_schema = 'public' and table_name = 'users'"
                )
            )
        ).all()
    }

    # then: deleted_at 테이블은 users뿐이고 퇴사 사유 컬럼·관련 CHECK가 없다
    assert tables == {"users"}
    assert "deleted_at" in user_columns
    assert "delete_reason" not in user_columns
    assert not {"ck_users_delete_reason_valid", "ck_users_deleted_pair"} & checks


async def test_every_foreign_key_column_leads_an_index(session: AsyncSession) -> None:
    """모든 FK 컬럼이 그 컬럼으로 시작하는 인덱스를 가진다.

    테스트 코드: SC-025
    """
    # when: check_schema 결과에서 선행 인덱스 규칙 위반만 고른다 (전제: head를 적용한 임시 DB)
    violations = [v for v in await check_schema(session) if v.rule.endswith("leading_index")]

    # then: 위반이 없다
    assert violations == []


async def test_only_owned_data_cascades(session: AsyncSession) -> None:
    """CASCADE FK는 소속 데이터 12개뿐이고 부모 테이블이 정해진 대로다.

    테스트 코드: SC-023
    """
    # when: ON DELETE CASCADE인 FK를 모두 읽는다 (전제: head를 적용한 임시 DB)
    cascades = {
        fk.table + "." + fk.column for fk in await foreign_keys(session) if fk.on_delete == "c"
    }

    # then: (테이블.컬럼) 집합이 소속 데이터 12개와 같다
    assert cascades == {
        "deal_partners.deal_id",
        "deal_bant_labels.deal_id",
        "deal_history.deal_id",
        "deal_actions.deal_id",
        "deal_attachments.deal_id",  # P2b: 첨부 메타데이터도 Deal 소속이다
        "forecast_snapshot_columns.snapshot_id",  # P6 R2 Q6: 저장 당시 코드 목록은 스냅숏 소속
        "forecast_snapshot_cells.snapshot_id",  # 셀은 (snapshot_id, forecast_key)로 열 소속
        "license_contracts.deal_id",  # 계약은 Deal 소속이다
        "license_contract_attachments.contract_id",  # 계약 첨부는 계약 소속이다
        "deal_comments.deal_id",  # Comment는 Deal 소속이다
        "deal_comments.action_id",  # Action Comment는 Action 소속이다(복합 FK)
        "user_password_hashes.user_id",  # 대체 로그인 해시는 사용자 소속(CASCADE_USER_FK_NAMES)
    }
    # then: 부모는 정해진 테이블이고 나머지는 deals다
    parents = {
        "user_password_hashes": {"users"},
        "license_contract_attachments": {"license_contracts"},
        "forecast_snapshot_columns": {"forecast_snapshots"},
        "forecast_snapshot_cells": {"forecast_snapshot_columns"},
        "deal_comments": {"deals", "deal_actions"},
    }
    assert all(
        fk.ref_table in parents.get(fk.table, {"deals"})
        for fk in await foreign_keys(session)
        if fk.on_delete == "c"
    )
