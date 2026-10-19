"""Feature: 운영자는 Action 유형 리비전을 올리고 내려 action_types와 deal_actions의 유형 FK를 둔다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 Vendor·Solution 리비전 다음이다.
보존 데이터 없음 전제(사용자 결정 2026-10-19)라 올리면 기존 deal_actions 행은 모두 지워지고, enum
컬럼 action_type은 action_type_id(NOT NULL, action_types FK RESTRICT)로 바뀐다. deal_history 행은
deal_actions를 가리키지 않아 그대로 남는다. 내리면 action_type 컬럼이 되살아나고 action_types가
사라진다(그 시점의 Action 행도 지운다).
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.factories_action_type import DEFAULT_ACTION_TYPE_NAMES
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
from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.revisions import action_types_revision, vendor_solution_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

OLD_ACTION_INSERT = (  # 이전 구조: action_type 문자열 컬럼
    "insert into deal_actions (id, deal_code, action_type, action, memo, next_action, due_date,"
    " acted_at, actor_user_id, status_key, forecast_key, created_at, updated_at) values (:id,"
    " :deal_code, 'meeting', :action, '', 'n', current_date, now(), :actor, 'prospecting',"
    " 'pipeline', now(), now())"
)
ACTION_HISTORY_INSERT = (
    "insert into deal_history (deal_code, changed_at, changed_by_user_id, category, target,"
    " before_text, after_text) values (:deal_code, now(), :actor, 'action', 'Action', '', :after)"
)
ACTION_COLUMNS = (
    "select column_name, data_type, is_nullable from information_schema.columns"
    " where table_name = 'deal_actions'"
)
TYPE_FK = (
    "select conname, confdeltype::text from pg_constraint"
    " where conrelid = 'deal_actions'::regclass and confrelid = 'action_types'::regclass"
)
OLD_SUMMARY = "등록: 미팅 · 킥오프 / Next Action: n (Due 2027-01-15)"


async def when_operator_upgrades(url: URL) -> None:
    """운영자 명령: Action 유형 리비전까지 올린다(head는 이후 리비전으로 앞서갈 수 있다)."""
    await upgrade_database(url, target=action_types_revision())


async def _deal_with_two_actions(session: AsyncSession) -> None:
    owner = await insert_user(session, "kim")
    customer = await insert_contact(session)
    code = await insert_deal(session, customer, owner)
    for name in ("첫째", "둘째"):
        params = {"id": uuid4(), "deal_code": code, "action": name, "actor": owner}
        await session.execute(text(OLD_ACTION_INSERT), params)
        history = {"deal_code": code, "actor": owner, "after": OLD_SUMMARY}
        await session.execute(text(ACTION_HISTORY_INSERT), history)


async def _action_count(url: URL) -> int:
    return int((await run_sql(url, "select count(*) from deal_actions"))[0][0])


async def test_upgrade_creates_action_types_with_the_eight_default_types(
    blank_database: URL,
) -> None:
    """Scenario: 올리면 action_types가 생기고 기본 유형 8개가 순서·기본 표시와 함께 들어간다."""
    # Given
    await given_schema_at(blank_database, vendor_solution_revision())
    assert "action_types" not in await table_names(blank_database)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, action_types_revision())
    rows = await run_sql(
        blank_database,
        "select name, is_default, default_order, created_by_user_id from action_types"
        " order by default_order",
    )
    assert [(r[0], r[1], r[2], r[3]) for r in rows] == [
        (name, True, order, None) for order, name in enumerate(DEFAULT_ACTION_TYPE_NAMES, start=1)
    ]


async def test_upgrade_deletes_existing_actions_and_keeps_history(blank_database: URL) -> None:
    """Scenario: Action 행이 있는 DB도 올라가고 Action 행은 모두 지워지며 History 문구는 남는다."""
    # Given
    await given_schema_at(blank_database, vendor_solution_revision())
    await given_rows(blank_database, _deal_with_two_actions)
    assert await _action_count(blank_database) == 2
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await _action_count(blank_database) == 0
    history = await run_sql(
        blank_database,
        "select after_text from deal_history where category = 'action' order by id",
    )
    assert [r[0] for r in history] == [OLD_SUMMARY, OLD_SUMMARY]


async def test_upgrade_keeps_deals_users_and_the_other_catalogs(blank_database: URL) -> None:
    """Scenario: Deal·사용자·BANT Label·코드는 그대로다(Action 행만 지워진다)."""
    # Given
    await given_schema_at(blank_database, vendor_solution_revision())
    await given_rows(blank_database, _deal_with_two_actions)
    labels = await run_sql(blank_database, "select count(*) from bant_labels")
    codes = await run_sql(blank_database, "select count(*) from codes")
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select count(*) from deals") == [(1,)]
    assert await run_sql(blank_database, "select count(*) from users") == [(1,)]
    assert await run_sql(blank_database, "select count(*) from bant_labels") == labels
    assert await run_sql(blank_database, "select count(*) from codes") == codes


async def test_upgrade_replaces_the_enum_column_with_a_restricting_foreign_key(
    blank_database: URL,
) -> None:
    """Scenario: action_type 컬럼이 없어지고 NOT NULL·FK RESTRICT인 action_type_id가 생긴다."""
    # Given
    await given_schema_at(blank_database, vendor_solution_revision())
    assert "action_type" in await column_names(blank_database, "deal_actions")
    # When
    await when_operator_upgrades(blank_database)
    # Then
    columns = {
        str(r[0]): (str(r[1]), str(r[2])) for r in await run_sql(blank_database, ACTION_COLUMNS)
    }
    assert "action_type" not in columns
    assert columns["action_type_id"] == ("uuid", "NO")
    assert [(r[0], r[1].strip()) for r in await run_sql(blank_database, TYPE_FK)] == [
        ("fk_deal_actions_action_type_id_action_types", "r")
    ]
    assert "ix_deal_actions_action_type_id" in await index_names(blank_database, "deal_actions")


async def test_upgrade_works_without_any_action(blank_database: URL) -> None:
    """Scenario: Action 행이 하나도 없는 DB에서도 올라간다."""
    # Given
    await given_schema_at(blank_database, vendor_solution_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, action_types_revision())
    assert await _action_count(blank_database) == 0


async def test_downgrade_restores_the_enum_column_and_removes_the_table(
    blank_database: URL,
) -> None:
    """Scenario: 내리면 action_type 컬럼이 되살아나고 action_types가 사라진다."""
    # Given
    await given_schema_at(blank_database, vendor_solution_revision())
    await when_operator_upgrades(blank_database)
    # When
    await when_operator_downgrades(blank_database, target=vendor_solution_revision())
    # Then
    await then_schema_is_at(blank_database, vendor_solution_revision())
    assert "action_types" not in await table_names(blank_database)
    columns = await column_names(blank_database, "deal_actions")
    assert "action_type" in columns
    assert "action_type_id" not in columns


async def test_downgrade_with_actions_deletes_them_and_succeeds(blank_database: URL) -> None:
    """Scenario: Action 행이 쌓인 head를 내려도 성공하고 그 시점의 Action 행은 지워진다."""
    # Given
    await given_schema_at(blank_database, action_types_revision())
    await given_rows(blank_database, _deal_with_a_typed_action)
    assert await _action_count(blank_database) == 1
    # When
    await when_operator_downgrades(blank_database, target=vendor_solution_revision())
    # Then
    assert await _action_count(blank_database) == 0
    assert await run_sql(blank_database, "select count(*) from deals") == [(1,)]


async def _deal_with_a_typed_action(session: AsyncSession) -> None:
    owner = await insert_user(session, "kim")
    customer = await insert_contact(session)
    code = await insert_deal(session, customer, owner)
    insert = (
        "insert into deal_actions (id, deal_code, action_type_id, action, memo, next_action,"
        " due_date, acted_at, actor_user_id, status_key, forecast_key, created_at, updated_at)"
        " values (:id, :deal_code, (select id from action_types where name = '미팅'), 'a', '',"
        " 'n', current_date, now(), :actor, 'prospecting', 'pipeline', now(), now())"
    )
    await session.execute(text(insert), {"id": uuid4(), "deal_code": code, "actor": owner})


async def test_downgrade_restores_the_deal_actions_structure_of_the_previous_revision(
    blank_database: URL,
) -> None:
    """Scenario: 내린 뒤 deal_actions 구조(열·제약·인덱스)는 올리기 전과 같다."""
    # Given
    await given_schema_at(blank_database, vendor_solution_revision())
    before = await table_structure(blank_database, "deal_actions")
    await when_operator_upgrades(blank_database)
    # When
    await when_operator_downgrades(blank_database, target=vendor_solution_revision())
    # Then
    assert await table_structure(blank_database, "deal_actions") == before


async def test_upgrade_after_downgrade_creates_the_same_structure_again(
    blank_database: URL,
) -> None:
    """Scenario: 내렸다가 다시 올려도 같은 구조와 같은 시드가 만들어진다."""
    # Given
    await given_schema_at(blank_database, vendor_solution_revision())
    await when_operator_upgrades(blank_database)
    first = {
        name: await table_structure(blank_database, name)
        for name in ("action_types", "deal_actions")
    }
    await when_operator_downgrades(blank_database, target=vendor_solution_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    second = {name: await table_structure(blank_database, name) for name in first}
    assert second == first
    names = await run_sql(blank_database, "select name from action_types order by default_order")
    assert [r[0] for r in names] == list(DEFAULT_ACTION_TYPE_NAMES)
    await then_schema_is_at(blank_database, action_types_revision())
