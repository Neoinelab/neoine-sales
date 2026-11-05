"""Feature: 운영자는 라이선스 계약 리비전을 올려 계약 테이블을 만들고 Won Deal마다 계약을 둔다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 개발 로그인 사용자 삭제 리비전
(`f2b7c9e4a615`) 바로 다음이다. 스키마상 순수 expand(`license_contracts`와
`license_contract_attachments` 추가, 기존 테이블 구조는 그대로)이고 데이터 삽입이 하나 있다:
forecast_key가 won인 Deal마다 미발급 계약 1건(기술담당 '', 점검주기 none, Note '', 등록자·수정자 =
Deal Owner). Won이 아닌 Deal에는 없다. 내리면 두 테이블만 사라진다(계약·첨부 메타 소실, 디스크
파일은 남는다).
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.schema import (
    given_rows,
    given_schema_at,
    index_names,
    table_names,
    table_structure,
    then_schema_is_at,
    when_operator_downgrades,
    when_operator_upgrades,
)
from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.revisions import license_contracts_revision, retire_dev_users_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

RESIGNED_AT = datetime(2026, 11, 1, tzinfo=UTC)
EXISTING_TABLES = ("users", "deals", "contacts", "deal_actions", "deal_attachments")
WON_A = "20261105-W001"
WON_B = "20261105-W002"
OPEN = "20261105-O001"
LOST = "20261105-L001"
CONTRACTS_PER_DEAL = (
    "select d.deal_code, count(c.id) from deals d"
    " left join license_contracts c on c.deal_id = d.id group by d.deal_code order by d.deal_code"
)


async def _seed(session: AsyncSession) -> None:
    """Won Deal 둘(하나는 퇴사한 Owner), 진행 중 Deal, Lost Deal."""
    customer = await insert_contact(session)
    kim = await insert_user(session, "kim")
    gone = await insert_user(session, "gone", deleted_at=RESIGNED_AT, delete_reason="resigned")
    won = {"status_key": "contract_completed", "forecast_key": "won"}
    await insert_deal(session, customer, owner_user_id=kim, code=WON_A, **won)
    await insert_deal(session, customer, owner_user_id=gone, code=WON_B, **won)
    await insert_deal(session, customer, owner_user_id=kim, code=OPEN)
    await insert_deal(session, customer, owner_user_id=kim, code=LOST, forecast_key="lost")


async def test_upgrade_creates_one_not_issued_contract_per_won_deal(blank_database: URL) -> None:
    """Scenario: 올리면 Won Deal마다 미발급 계약이 정확히 1건이고 Won이 아닌 Deal에는 없다."""
    # Given
    await given_schema_at(blank_database, retire_dev_users_revision())
    await given_rows(blank_database, _seed)
    # When
    await when_operator_upgrades(blank_database, target=license_contracts_revision())
    # Then
    await then_schema_is_at(blank_database, license_contracts_revision())
    assert await run_sql(blank_database, CONTRACTS_PER_DEAL) == [
        (LOST, 0),
        (OPEN, 0),
        (WON_A, 1),
        (WON_B, 1),
    ]
    rows = await run_sql(
        blank_database,
        "select status, license_start, license_end, term_amount, term_unit, tech_owner,"
        " inspection_cycle, note, renewed_from_id, ended_at from license_contracts",
    )
    assert rows == [("not_issued", None, None, None, None, "", "none", "", None, None)] * 2


async def test_the_generated_contracts_are_registered_by_the_deal_owner(
    blank_database: URL,
) -> None:
    """Scenario: 자동 생성 계약의 등록자·수정자는 Deal Owner다(퇴사한 Owner여도 FK가 유효하다)."""
    # Given
    await given_schema_at(blank_database, retire_dev_users_revision())
    await given_rows(blank_database, _seed)
    # When
    await when_operator_upgrades(blank_database, target=license_contracts_revision())
    # Then
    rows = await run_sql(
        blank_database,
        "select d.deal_code, d.owner_user_id = c.created_by_user_id,"
        " c.created_by_user_id = c.updated_by_user_id, c.created_at is not null,"
        " c.updated_at is not null from license_contracts c join deals d on d.id = c.deal_id"
        " order by d.deal_code",
    )
    assert rows == [(WON_A, True, True, True, True), (WON_B, True, True, True, True)]


async def test_upgrade_with_no_deals_leaves_the_new_tables_empty(blank_database: URL) -> None:
    """Scenario: Deal이 없으면 두 테이블이 비어 있다."""
    # Given
    await given_schema_at(blank_database, retire_dev_users_revision())
    # When
    await when_operator_upgrades(blank_database, target=license_contracts_revision())
    # Then
    assert await run_sql(blank_database, "select count(*) from license_contracts") == [(0,)]
    assert await run_sql(blank_database, "select count(*) from license_contract_attachments") == [
        (0,)
    ]


async def test_upgrade_creates_the_tables_the_partial_unique_index_and_the_checks(
    blank_database: URL,
) -> None:
    """Scenario: 올리면 두 테이블, 발급 부분 유니크 인덱스, CHECK가 생긴다."""
    # Given
    await given_schema_at(blank_database, retire_dev_users_revision())
    before = await table_names(blank_database)
    # When
    await when_operator_upgrades(blank_database, target=license_contracts_revision())
    # Then
    assert await table_names(blank_database) == before | {
        "license_contracts",
        "license_contract_attachments",
    }
    assert "uq_license_contracts_deal_id_issued" in await index_names(
        blank_database, "license_contracts"
    )
    checks = {
        str(row[0])
        for row in await run_sql(
            blank_database,
            "select conname from pg_constraint"
            " where conrelid = 'license_contracts'::regclass and contype = 'c'",
        )
    }
    assert {
        "ck_license_contracts_status",
        "ck_license_contracts_inspection_cycle",
        "ck_license_contracts_term_amount",
        "ck_license_contracts_term_unit",
        "ck_license_contracts_term_complete",
        "ck_license_contracts_not_issued_no_term",
        "ck_license_contracts_issued_has_term",
        "ck_license_contracts_end_after_start",
        "ck_license_contracts_ended_has_time",
    } <= checks


async def test_upgrade_changes_no_existing_table_structure_and_keeps_rows(
    blank_database: URL,
) -> None:
    """Scenario: 기존 테이블 구조와 행은 그대로다(순수 expand)."""
    # Given
    await given_schema_at(blank_database, retire_dev_users_revision())
    await given_rows(blank_database, _seed)
    before = {name: await table_structure(blank_database, name) for name in EXISTING_TABLES}
    users = await run_sql(blank_database, "select count(*) from users")
    deals = await run_sql(blank_database, "select count(*) from deals")
    # When
    await when_operator_upgrades(blank_database, target=license_contracts_revision())
    # Then
    after = {name: await table_structure(blank_database, name) for name in EXISTING_TABLES}
    assert after == before
    assert await run_sql(blank_database, "select count(*) from users") == users
    assert await run_sql(blank_database, "select count(*) from deals") == deals


async def test_upgrade_to_head_passes_the_license_contracts_revision(blank_database: URL) -> None:
    """Scenario: 빈 DB를 head까지 올리면 두 테이블이 있고 head는 이 리비전이다."""
    # Given
    # (마이그레이션이 하나도 적용되지 않은 빈 DB)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, license_contracts_revision())
    assert {"license_contracts", "license_contract_attachments"} <= await table_names(
        blank_database
    )


async def test_downgrade_drops_only_the_two_tables(blank_database: URL) -> None:
    """Scenario: 내리면 두 테이블만 사라지고 기존 테이블 구조와 행은 올리기 전과 같다."""
    # Given
    await given_schema_at(blank_database, retire_dev_users_revision())
    await given_rows(blank_database, _seed)
    before_tables = await table_names(blank_database)
    before = {name: await table_structure(blank_database, name) for name in EXISTING_TABLES}
    await when_operator_upgrades(blank_database, target=license_contracts_revision())
    # When
    await when_operator_downgrades(blank_database, target=retire_dev_users_revision())
    # Then
    await then_schema_is_at(blank_database, retire_dev_users_revision())
    assert await table_names(blank_database) == before_tables
    assert {name: await table_structure(blank_database, name) for name in EXISTING_TABLES} == before
    assert await run_sql(blank_database, "select count(*) from deals") == [(4,)]
