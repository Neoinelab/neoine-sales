"""Feature: 운영자는 Next Action 상태 리비전을 올리고 내려 deal_actions의 입력 분리와 상태를 둔다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 Action 유형 리비전 다음이다.
올리면 action·next_action·due_date가 NULL을 허용하고 next_action_status(기본 open)와
next_action_closed_at이 생기며, 기존 행은 값 그대로 모두 open이 된다(행은 지우지 않는다).
CHECK 4개가 함께 생긴다. 내릴 때 NULL이 든 행이 있으면 데이터를 지우지 않고 중단한다
(2026-10-15 예외: 보존 데이터가 없으므로 upgrade 데이터 이전은 없고 downgrade 사전 점검만 둔다).
"""

from datetime import date
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.functional.steps.schema import (
    given_rows,
    given_schema_at,
    table_structure,
    then_command_aborted,
    then_command_succeeded,
    then_schema_is_at,
    when_operator_attempts_downgrade,
    when_operator_downgrades,
)
from tests.functional.steps.schema import when_operator_upgrades as upgrade_database
from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.revisions import action_types_revision, next_action_status_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMNS = (
    "select column_name, is_nullable, column_default from information_schema.columns"
    " where table_name = 'deal_actions' and column_name in ('action', 'next_action', 'due_date',"
    " 'next_action_status', 'next_action_closed_at') order by column_name"
)
CHECK_NAMES = (
    "select conname from pg_constraint where conrelid = 'deal_actions'::regclass"
    " and contype = 'c' order by conname"
)
NEW_CHECKS = [
    "ck_deal_actions_action_or_next",
    "ck_deal_actions_next_action_closed_at",
    "ck_deal_actions_next_action_fields",
    "ck_deal_actions_next_action_status",
]
OLD_INSERT = (
    "insert into deal_actions (id, deal_code, action_type_id, action, memo, next_action, due_date,"
    " acted_at, actor_user_id, status_key, forecast_key, created_at, updated_at) values (:id,"
    " :deal_code, (select id from action_types where name = '미팅'), :action, :memo, :next_action,"
    " :due_date, now(), :actor, 'prospecting', 'pipeline', now(), now())"
)
NULL_ROW_INSERT = (
    "insert into deal_actions (id, deal_code, action_type_id, action, memo, next_action, due_date,"
    " next_action_status, acted_at, actor_user_id, status_key, forecast_key, created_at,"
    " updated_at) values (:id, :deal_code, (select id from action_types where name = '미팅'),"
    " '진행만', '', null, null, null, now(), :actor, 'prospecting', 'pipeline', now(), now())"
)


async def when_operator_upgrades(url: URL) -> None:
    """운영자 명령: Next Action 상태 리비전까지 올린다(head는 이후 리비전으로 앞서갈 수 있다)."""
    await upgrade_database(url, target=next_action_status_revision())


async def _deal_with_two_old_actions(session: AsyncSession) -> None:
    owner = await insert_user(session, "kim")
    customer = await insert_contact(session)
    code = await insert_deal(session, customer, owner)
    for number in (1, 2):
        params = {
            "id": uuid4(),
            "deal_code": code,
            "action": f"진행 {number}",
            "memo": f"메모 {number}",
            "next_action": f"계획 {number}",
            "due_date": date(2027, 1, number),
            "actor": owner,
        }
        await session.execute(text(OLD_INSERT), params)


async def _deal_with_a_progress_only_action(session: AsyncSession) -> None:
    owner = await insert_user(session, "kim")
    customer = await insert_contact(session)
    code = await insert_deal(session, customer, owner)
    await session.execute(text(NULL_ROW_INSERT), {"id": uuid4(), "deal_code": code, "actor": owner})


async def test_upgrade_keeps_existing_actions_and_makes_them_open(blank_database: URL) -> None:
    """Scenario: 기존 Action은 값 그대로 모두 open이 되고 종료 시각은 null이다."""
    # Given
    await given_schema_at(blank_database, action_types_revision())
    await given_rows(blank_database, _deal_with_two_old_actions)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, next_action_status_revision())
    rows = await run_sql(
        blank_database,
        "select action, memo, next_action, due_date::text, next_action_status,"
        " next_action_closed_at from deal_actions order by action",
    )
    assert [tuple(r) for r in rows] == [
        ("진행 1", "메모 1", "계획 1", "2027-01-01", "open", None),
        ("진행 2", "메모 2", "계획 2", "2027-01-02", "open", None),
    ]


async def test_upgrade_makes_the_plan_fields_nullable_and_adds_the_status_columns(
    blank_database: URL,
) -> None:
    """Scenario: action·next_action·due_date가 NULL을 허용하고 상태 컬럼이 생긴다."""
    # Given
    await given_schema_at(blank_database, action_types_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    columns = {str(r[0]): (str(r[1]), r[2]) for r in await run_sql(blank_database, COLUMNS)}
    assert set(columns) == {
        "action",
        "next_action",
        "due_date",
        "next_action_status",
        "next_action_closed_at",
    }
    assert all(nullable == "YES" for nullable, _ in columns.values())
    assert "open" in str(columns["next_action_status"][1])
    assert columns["next_action_closed_at"][1] is None


async def test_upgrade_adds_the_four_checks(blank_database: URL) -> None:
    """Scenario: 입력 분리·상태 규칙을 지키는 CHECK 4개가 생긴다."""
    # Given
    await given_schema_at(blank_database, action_types_revision())
    before = {str(r[0]) for r in await run_sql(blank_database, CHECK_NAMES)}
    # When
    await when_operator_upgrades(blank_database)
    # Then
    after = {str(r[0]) for r in await run_sql(blank_database, CHECK_NAMES)}
    assert sorted(after - before) == NEW_CHECKS


async def test_upgrade_works_without_any_action(blank_database: URL) -> None:
    """Scenario: Action 행이 하나도 없는 DB에서도 올라간다."""
    # Given
    await given_schema_at(blank_database, action_types_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, next_action_status_revision())


async def test_downgrade_restores_the_previous_structure(blank_database: URL) -> None:
    """Scenario: 내리면 NOT NULL·컬럼·CHECK가 이전 리비전과 같은 구조로 돌아온다."""
    # Given
    await given_schema_at(blank_database, action_types_revision())
    before = await table_structure(blank_database, "deal_actions")
    await when_operator_upgrades(blank_database)
    # When
    await when_operator_downgrades(blank_database, target=action_types_revision())
    # Then
    await then_schema_is_at(blank_database, action_types_revision())
    assert await table_structure(blank_database, "deal_actions") == before


async def test_downgrade_keeps_rows_that_can_be_converted(blank_database: URL) -> None:
    """Scenario: 모든 행에 값이 있으면 내려도 행이 그대로 남는다."""
    # Given
    await given_schema_at(blank_database, action_types_revision())
    await given_rows(blank_database, _deal_with_two_old_actions)
    await when_operator_upgrades(blank_database)
    # When
    outcome = await when_operator_attempts_downgrade(blank_database, target=action_types_revision())
    # Then
    then_command_succeeded(outcome)
    assert await run_sql(blank_database, "select count(*) from deal_actions") == [(2,)]


async def test_downgrade_aborts_without_deleting_when_a_row_has_null_plan_fields(
    blank_database: URL,
) -> None:
    """Scenario: 진행사항만 있는 행이 있으면 내리기가 중단되고 행·스키마가 그대로다."""
    # Given
    await given_schema_at(blank_database, next_action_status_revision())
    await given_rows(blank_database, _deal_with_a_progress_only_action)
    # When
    outcome = await when_operator_attempts_downgrade(blank_database, target=action_types_revision())
    # Then
    then_command_aborted(outcome)
    await then_schema_is_at(blank_database, next_action_status_revision())
    assert await run_sql(blank_database, "select count(*) from deal_actions") == [(1,)]


async def test_upgrade_after_downgrade_creates_the_same_structure_again(
    blank_database: URL,
) -> None:
    """Scenario: 내렸다가 다시 올려도 같은 구조가 만들어진다."""
    # Given
    await given_schema_at(blank_database, action_types_revision())
    await when_operator_upgrades(blank_database)
    first = await table_structure(blank_database, "deal_actions")
    await when_operator_downgrades(blank_database, target=action_types_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await table_structure(blank_database, "deal_actions") == first
    await then_schema_is_at(blank_database, next_action_status_revision())
