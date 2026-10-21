"""Feature: 운영자는 Deal users 필수 리비전을 올리고 내려 deals.users를 NOT NULL·0 이상으로 둔다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 Next Action 상태 리비전 다음이다.
올리면 users가 NULL인 행은 0이 되고(값이 있던 행은 그대로, 다른 컬럼은 변하지 않음) users는
NOT NULL, CHECK는 `users >= 0`이 된다. 내리면 0인 행이 NULL로 돌아가고(1 이상은 그대로)
구조는 이전 리비전과 같아진다(2026-10-21 사용자 결정: 사전 점검 중단 없음).
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.schema import (
    given_rows,
    given_schema_at,
    table_structure,
    then_schema_is_at,
    when_operator_downgrades,
)
from tests.functional.steps.schema import when_operator_upgrades as upgrade_database
from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.revisions import deals_users_required_revision, next_action_status_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

NULL_CODE = "20261016-A001"
SEVEN_CODE = "20261016-A002"
ZERO_CODE = "20261016-A003"
USERS_COLUMN = (
    "select is_nullable from information_schema.columns"
    " where table_name = 'deals' and column_name = 'users'"
)
USERS_CHECK = (
    "select pg_get_constraintdef(oid) from pg_constraint where conname = 'ck_deals_users_positive'"
)
OTHER_COLUMNS = (
    "select deal_code, name, owner_user_id::text, status_key, forecast_key, revenue_amount,"
    " revenue_date::text, procurement, created_at::text, updated_at::text from deals"
    " order by deal_code"
)
USERS_BY_CODE = "select deal_code, users from deals order by deal_code"


async def when_operator_upgrades(url: URL) -> None:
    """운영자 명령: users 필수 리비전까지 올린다(head는 이후 리비전으로 앞서갈 수 있다)."""
    await upgrade_database(url, target=deals_users_required_revision())


async def _deals_with_null_and_seven(session: AsyncSession) -> None:
    owner = await insert_user(session, "kim")
    customer = await insert_contact(session)
    await insert_deal(session, customer, owner, code=NULL_CODE, users=None)
    await insert_deal(session, customer, owner, code=SEVEN_CODE, users=7)


async def _deals_with_seven_and_zero(session: AsyncSession) -> None:
    owner = await insert_user(session, "kim")
    customer = await insert_contact(session)
    await insert_deal(session, customer, owner, code=SEVEN_CODE, users=7)
    await insert_deal(session, customer, owner, code=ZERO_CODE, users=0)


async def test_upgrade_fills_missing_users_with_zero(blank_database: URL) -> None:
    """Scenario: users가 NULL이던 Deal은 올린 뒤 0이 된다."""
    # Given
    await given_schema_at(blank_database, next_action_status_revision())
    await given_rows(blank_database, _deals_with_null_and_seven)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, deals_users_required_revision())
    rows = await run_sql(blank_database, USERS_BY_CODE)
    assert dict(map(tuple, rows)) == {NULL_CODE: 0, SEVEN_CODE: 7}


async def test_upgrade_keeps_existing_users_values_and_other_columns(blank_database: URL) -> None:
    """Scenario: 값이 있던 행은 그대로이고 다른 컬럼은 어느 행도 바뀌지 않는다(updated_at 포함)."""
    # Given
    await given_schema_at(blank_database, next_action_status_revision())
    await given_rows(blank_database, _deals_with_null_and_seven)
    before = [tuple(r) for r in await run_sql(blank_database, OTHER_COLUMNS)]
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert [tuple(r) for r in await run_sql(blank_database, OTHER_COLUMNS)] == before
    users = dict(map(tuple, await run_sql(blank_database, USERS_BY_CODE)))
    assert users[SEVEN_CODE] == 7


async def test_upgrade_works_without_any_deal(blank_database: URL) -> None:
    """Scenario: Deal이 하나도 없는 DB에서도 올라간다."""
    # Given
    await given_schema_at(blank_database, next_action_status_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, deals_users_required_revision())


async def test_upgrade_makes_users_not_null_with_a_non_negative_check(blank_database: URL) -> None:
    """Scenario: 올리면 users는 NOT NULL이고 CHECK는 users >= 0(NULL 허용 조건 없음)이다."""
    # Given
    await given_schema_at(blank_database, next_action_status_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert [tuple(r) for r in await run_sql(blank_database, USERS_COLUMN)] == [("NO",)]
    definition = str((await run_sql(blank_database, USERS_CHECK))[0][0])
    assert "users >= 0" in definition
    assert "IS NULL" not in definition.upper()


async def test_downgrade_turns_zero_back_into_null_and_restores_the_structure(
    blank_database: URL,
) -> None:
    """Scenario: 내리면 0인 행은 NULL, 1 이상은 그대로이고 deals 구조가 이전 리비전과 같다."""
    # Given
    await given_schema_at(blank_database, next_action_status_revision())
    before = await table_structure(blank_database, "deals")
    await when_operator_upgrades(blank_database)
    await given_rows(blank_database, _deals_with_seven_and_zero)
    # When
    await when_operator_downgrades(blank_database, target=next_action_status_revision())
    # Then
    await then_schema_is_at(blank_database, next_action_status_revision())
    rows = await run_sql(blank_database, USERS_BY_CODE)
    assert dict(map(tuple, rows)) == {SEVEN_CODE: 7, ZERO_CODE: None}
    assert await table_structure(blank_database, "deals") == before


async def test_upgrade_after_downgrade_creates_the_same_structure_again(
    blank_database: URL,
) -> None:
    """Scenario: 올렸다 내린 뒤 다시 올려도 처음 올렸을 때와 같은 구조다."""
    # Given
    await given_schema_at(blank_database, next_action_status_revision())
    await when_operator_upgrades(blank_database)
    first = await table_structure(blank_database, "deals")
    await when_operator_downgrades(blank_database, target=next_action_status_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await table_structure(blank_database, "deals") == first
