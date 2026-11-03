"""Feature: 운영자는 파트너 미팅 Deal 제거 리비전을 올려 partner_meetings에서 Deal 연결을 없앤다.

When: 운영자 명령(alembic upgrade). 이 리비전은 앱 자체 계정 리비전 다음이고 head다.
`deal_id` 컬럼·FK `fk_partner_meetings_deal_id_deals`·인덱스 `ix_partner_meetings_deal_id`를 한 번에
없애며(expand/contract 예외, 보존 데이터 없음) 기존 미팅 행은 지우지 않는다(회사·날짜·내용·작성자
보존). downgrade는 되돌리지 않고 항상 거부한다(복구는 백업 복원뿐).
"""

from datetime import date
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
    then_command_aborted,
    then_schema_is_at,
    when_operator_attempts_downgrade,
    when_operator_upgrades,
)
from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.ids import new_id
from tests.support.revisions import auth_mode_revision, partner_meetings_drop_deal_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

OTHER_TABLES = ("users", "deals", "contacts", "deal_actions", "reports")
INSERT_OLD_MEETING = (
    "insert into partner_meetings (id, deal_id, partner_company, meeting_date, content,"
    " created_by_user_id, created_at, updated_at)"
    " values (:id, (select id from deals where deal_code = :code), :company, :day, :content,"
    " :author, now(), now())"
)
CONSTRAINTS = (
    "select conname from pg_constraint where conrelid = 'partner_meetings'::regclass"
    " order by conname"
)


async def _users_and_deal(session: AsyncSession) -> None:
    author = await insert_user(session, "kim")
    customer = await insert_contact(session)
    await insert_deal(session, customer, owner_user_id=author, code="20261016-A001")


async def _two_meetings(session: AsyncSession) -> None:
    await _users_and_deal(session)
    author = (await session.execute(text("select id from users where login_id = 'kim'"))).scalar()
    rows = (
        ("한빛파트너스", date(2026, 10, 1), "킥오프\n다음 주"),
        ("Acme", date(2026, 11, 5), "계약"),
    )
    for company, day, content in rows:
        await session.execute(
            text(INSERT_OLD_MEETING),
            {
                "id": new_id(),
                "code": "20261016-A001",
                "company": company,
                "day": day,
                "content": content,
                "author": author,
            },
        )


async def test_upgrade_drops_the_deal_link_and_keeps_existing_meetings(
    blank_database: URL,
) -> None:
    """Scenario: 올리면 deal_id·FK·인덱스가 없어지고 기존 미팅 두 건의 내용은 그대로다."""
    # Given
    await given_schema_at(blank_database, auth_mode_revision())
    await given_rows(blank_database, _two_meetings)
    assert "deal_id" in await column_names(blank_database, "partner_meetings")
    before = await run_sql(
        blank_database,
        "select partner_company, meeting_date, content, created_by_user_id"
        " from partner_meetings order by meeting_date",
    )
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, partner_meetings_drop_deal_revision())
    assert "deal_id" not in await column_names(blank_database, "partner_meetings")
    assert "fk_partner_meetings_deal_id_deals" not in {
        str(r[0]) for r in await run_sql(blank_database, CONSTRAINTS)
    }
    assert "ix_partner_meetings_deal_id" not in await index_names(
        blank_database, "partner_meetings"
    )
    after = await run_sql(
        blank_database,
        "select partner_company, meeting_date, content, created_by_user_id"
        " from partner_meetings order by meeting_date",
    )
    assert len(after) == 2
    assert after == before


async def test_upgrade_keeps_the_remaining_columns_checks_and_indexes(blank_database: URL) -> None:
    """Scenario: 나머지 컬럼·CHECK 2개·인덱스 2개·작성자 FK는 그대로이고 다른 테이블도 그대로다."""
    # Given
    await given_schema_at(blank_database, auth_mode_revision())
    before = {name: await table_structure(blank_database, name) for name in OTHER_TABLES}
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await column_names(blank_database, "partner_meetings") == {
        "id",
        "partner_company",
        "meeting_date",
        "content",
        "created_by_user_id",
        "created_at",
        "updated_at",
    }
    constraints = {str(r[0]) for r in await run_sql(blank_database, CONSTRAINTS)}
    assert {
        "ck_partner_meetings_content_not_blank",
        "ck_partner_meetings_company_valid",
        "fk_partner_meetings_created_by_user_id_users",
    } <= constraints
    assert {"ix_partner_meetings_meeting_date_id", "ix_partner_meetings_created_by_user_id"} <= (
        await index_names(blank_database, "partner_meetings")
    )
    assert {name: await table_structure(blank_database, name) for name in OTHER_TABLES} == before
    assert "partner_meetings" in await table_names(blank_database)


async def test_upgrade_from_empty_to_head_ends_at_the_drop_deal_revision(
    blank_database: URL,
) -> None:
    """Scenario: 빈 DB를 head로 올리면 이 리비전에 이르고 partner_meetings에 deal_id가 없다."""
    # Given
    # (마이그레이션이 하나도 적용되지 않은 빈 DB)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, partner_meetings_drop_deal_revision())
    assert "deal_id" not in await column_names(blank_database, "partner_meetings")


async def test_downgrade_is_always_refused(blank_database: URL) -> None:
    """Scenario: 내리기는 거부되고 스키마는 이 리비전 그대로다(복구는 백업 복원뿐)."""
    # Given
    await when_operator_upgrades(blank_database)
    # When
    outcome = await when_operator_attempts_downgrade(blank_database, target=auth_mode_revision())
    # Then
    then_command_aborted(outcome)
    await then_schema_is_at(blank_database, partner_meetings_drop_deal_revision())
    assert "deal_id" not in await column_names(blank_database, "partner_meetings")
