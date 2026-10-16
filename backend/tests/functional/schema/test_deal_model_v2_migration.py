"""Feature: 운영자는 Deal 모델 재구성 리비전(M-P1)을 올리고 내려 새 구조를 본다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 연락처 통합 리비전(`66ebcb3da2da`)
다음이다. 보존 데이터 없음 전제(사용자 결정 2026-10-15)라 올리면 deals·deal_actions·
deal_stage_changes의 행은 삭제되고 새 구조로 다시 만들어진다. 내리면 이전 리비전의 구조가
정확히 복원된다(빈 테이블).
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from tests.functional.steps.schema import (
    column_names,
    given_rows,
    given_schema_at,
    index_names,
    table_names,
    table_structure,
    then_schema_is_at,
    when_operator_downgrades,
)
from tests.functional.steps.schema import when_operator_upgrades as upgrade_database
from tests.support.revisions import CONTACTS_REVISION, deal_model_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def when_operator_upgrades(url: URL) -> None:
    """운영자 명령: M-P1 리비전까지 올린다(head는 이후 리비전(P2 M-P2)으로 앞서간다)."""
    await upgrade_database(url, target=deal_model_revision())


NEW_TABLES = {"deal_partners", "deal_bant_labels", "deal_history"}
OLD_STRUCTURE_TABLES = ("deals", "deal_actions", "deal_stage_changes", "codes", "bant_labels")
SEED_COUNTS = "select kind, count(*) from codes group by kind order by kind"
DEAL_COLUMNS = {
    "deal_code",
    "name",
    "owner_user_id",
    "vendor",
    "solution",
    "users",
    "status_kind",
    "status_key",
    "forecast_kind",
    "forecast_key",
    "revenue_amount",
    "revenue_date",
    "customer_id",
    "quote_submitted",
    "quote_submitted_date",
    "poc_state",
    "poc_completed_date",
    "procurement",
    "created_at",
    "updated_at",
}


async def _seed_legacy_deal(session: AsyncSession) -> None:
    """이전 리비전 스키마(id, code, stage ...)에 Deal·활동·단계 이력 한 건씩을 넣는다."""
    user = (
        await session.execute(
            text(
                "insert into users (id, login_id, role, created_by_user_id, created_at, updated_at)"
                " values (:id, 'old', 'sales', :id, now(), now()) returning id"
            ),
            {"id": "00000000-0000-4000-8000-0000000000aa"},
        )
    ).scalar_one()
    await session.execute(
        text(
            "insert into contacts (id, kind, company, name, created_at, updated_at)"
            " values ('00000000-0000-4000-8000-0000000000bb', 'customer', '회사', '담당',"
            " now(), now())"
        )
    )
    await session.execute(
        text(
            "insert into deals (id, code, name, owner_user_id, vendor, solution, revenue_amount,"
            " revenue_currency, revenue_date, customer_id, created_at, updated_at)"
            " values ('00000000-0000-4000-8000-0000000000cc', 'OLD-1', 'n', :user, 'v', 's', 100,"
            " 'KRW', current_date, '00000000-0000-4000-8000-0000000000bb', now(), now())"
        ),
        {"user": user},
    )
    await session.execute(
        text(
            "insert into deal_actions (id, deal_id, action_type, action, memo, next_action,"
            " due_date, acted_at, actor_user_id, created_at, updated_at) values"
            " (gen_random_uuid(), '00000000-0000-4000-8000-0000000000cc', 'call', 'a', '', 'n',"
            " current_date, now(), :user, now(), now())"
        ),
        {"user": user},
    )
    await session.execute(
        text(
            "insert into deal_stage_changes (id, deal_id, from_stage, to_stage, reason,"
            " changed_by_user_id, changed_at) values (gen_random_uuid(),"
            " '00000000-0000-4000-8000-0000000000cc', 'prospecting', 'introduction', null, :user,"
            " now())"
        ),
        {"user": user},
    )


async def test_upgrade_creates_the_new_deal_tables_and_drops_the_stage_change_table(
    blank_database: URL,
) -> None:
    """Scenario: 올리면 파트너 링크·BANT 선택·이력 테이블이 생기고 단계 이력 테이블은 사라진다."""
    # Given
    await given_schema_at(blank_database, CONTACTS_REVISION)
    assert "deal_stage_changes" in await table_names(blank_database)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, deal_model_revision())
    tables = await table_names(blank_database)
    assert tables >= NEW_TABLES
    assert "deal_stage_changes" not in tables


async def test_upgrade_replaces_the_deals_columns_with_the_new_model(blank_database: URL) -> None:
    """Scenario: 올리면 deal_code가 PK인 새 컬럼 집합이 되고 구 컬럼은 없다."""
    # Given
    await given_schema_at(blank_database, CONTACTS_REVISION)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await column_names(blank_database, "deals") == DEAL_COLUMNS
    assert "deal_code" in await column_names(blank_database, "deal_actions")
    assert "deal_id" not in await column_names(blank_database, "deal_actions")
    pk = await run_sql(
        blank_database,
        "select a.attname from pg_constraint c join pg_attribute a"
        " on a.attrelid = c.conrelid and a.attnum = any(c.conkey)"
        " where c.conrelid = 'deals'::regclass and c.contype = 'p'",
    )
    assert {str(row[0]) for row in pk} == {"deal_code"}


async def test_upgrade_creates_the_constraints_and_the_filter_indexes(blank_database: URL) -> None:
    """Scenario: 올리면 CHECK·부분 유니크·복합 FK와 목록 필터·정렬 인덱스가 생긴다."""
    # Given
    await given_schema_at(blank_database, CONTACTS_REVISION)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    constraints = await run_sql(
        blank_database, "select conname from pg_constraint where conrelid = 'deals'::regclass"
    )
    assert {
        "ck_deals_code_format",
        "ck_deals_amount_range",
        "ck_deals_users_positive",
        "ck_deals_won_sync",
        "fk_deals_status_code",
        "fk_deals_forecast_code",
    } <= {str(r[0]) for r in constraints}
    assert {
        "ix_deals_owner_user_id",
        "ix_deals_status_key",
        "ix_deals_forecast_key",
        "ix_deals_revenue_date",
        "ix_deals_updated_at",
    } <= await index_names(blank_database, "deals")
    assert "uq_deal_partners_one_active" in await index_names(blank_database, "deal_partners")
    assert "ix_deal_actions_deal_code_acted_at" in await index_names(blank_database, "deal_actions")


async def test_upgrade_keeps_the_codes_and_labels_seed(blank_database: URL) -> None:
    """Scenario: 올려도 코드·Label 시드는 그대로이고 codes(kind, key)는 이름 있는 제약이 된다."""
    # Given
    await given_schema_at(blank_database, CONTACTS_REVISION)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, SEED_COUNTS) == [("forecast", 6), ("status", 7)]
    assert await run_sql(blank_database, "select count(*) from bant_labels") == [(23,)]
    unique = await run_sql(
        blank_database,
        "select conname from pg_constraint where conrelid = 'codes'::regclass"
        " and conname = 'uq_codes_kind_key' and contype = 'u'",
    )
    assert [str(r[0]) for r in unique] == ["uq_codes_kind_key"]


async def test_upgrade_discards_the_old_deal_rows_because_nothing_is_preserved(
    blank_database: URL,
) -> None:
    """Scenario: 보존 데이터가 없다는 전제라 올리면 기존 Deal·활동·단계 이력 행은 삭제된다."""
    # Given
    await given_schema_at(blank_database, CONTACTS_REVISION)
    await given_rows(blank_database, _seed_legacy_deal)
    assert await run_sql(blank_database, "select count(*) from deals") == [(1,)]
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select count(*) from deals") == [(0,)]
    assert await run_sql(blank_database, "select count(*) from deal_actions") == [(0,)]
    assert await run_sql(blank_database, "select count(*) from contacts") == [
        (1,)
    ]  # 연락처는 남는다


async def test_downgrade_restores_the_exact_structure_of_the_previous_revision(
    blank_database: URL,
) -> None:
    """Scenario: 내리면 deals·활동·단계 이력·코드·Label이 이전 리비전과 열·제약·인덱스까지 같다."""
    # Given
    await given_schema_at(blank_database, CONTACTS_REVISION)
    before = {t: await table_structure(blank_database, t) for t in OLD_STRUCTURE_TABLES}
    await when_operator_upgrades(blank_database)
    # When
    await when_operator_downgrades(blank_database, target=CONTACTS_REVISION)
    # Then
    await then_schema_is_at(blank_database, CONTACTS_REVISION)
    after = {t: await table_structure(blank_database, t) for t in OLD_STRUCTURE_TABLES}
    assert after == before
    assert not NEW_TABLES & await table_names(blank_database)


async def test_downgrade_leaves_the_seed_and_contacts_in_place(blank_database: URL) -> None:
    """Scenario: 내려도 코드·Label 시드와 연락처 테이블은 그대로다."""
    # Given
    await given_schema_at(blank_database, CONTACTS_REVISION)
    await when_operator_upgrades(blank_database)
    # When
    await when_operator_downgrades(blank_database, target=CONTACTS_REVISION)
    # Then
    assert await run_sql(blank_database, SEED_COUNTS) == [("forecast", 6), ("status", 7)]
    assert await run_sql(blank_database, "select count(*) from bant_labels") == [(23,)]
    assert "contacts" in await table_names(blank_database)


async def test_upgrade_after_downgrade_creates_the_new_structure_again(blank_database: URL) -> None:
    """Scenario: 내렸다가 다시 올려도 같은 새 구조가 만들어진다."""
    # Given
    await given_schema_at(blank_database, CONTACTS_REVISION)
    await when_operator_upgrades(blank_database)
    first = {t: await table_structure(blank_database, t) for t in ("deals", "deal_history")}
    await when_operator_downgrades(blank_database, target=CONTACTS_REVISION)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, deal_model_revision())
    again = {t: await table_structure(blank_database, t) for t in ("deals", "deal_history")}
    assert again == first
