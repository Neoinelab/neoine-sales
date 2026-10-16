"""Feature: 운영자는 Action 스냅숏 리비전(M-P2)을 올리고 내려 새 구조를 본다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 Deal 모델 재구성 리비전(M-P1) 다음이다.
보존 데이터 없음 전제(사용자 결정 2026-10-15)라 올리면 deal_actions의 행은 삭제되고, Status/Forecast
스냅숏 컬럼(NOT NULL, codes 복합 FK)이 생기며 진행사항·Next Action·Memo가 TEXT가 된다. 내리면
이전 리비전의 구조가 정확히 복원된다(행이 있으면 먼저 지운다).
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.functional.steps.schema import (
    column_names,
    given_rows,
    given_schema_at,
    table_structure,
    then_schema_is_at,
    when_operator_downgrades,
)
from tests.functional.steps.schema import when_operator_upgrades as upgrade_database
from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.revisions import action_snapshot_revision, deal_model_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def when_operator_upgrades(url: URL) -> None:
    """운영자 명령: M-P2 리비전까지 올린다(head는 이후 리비전으로 앞서갈 수 있다)."""
    await upgrade_database(url, target=action_snapshot_revision())


SNAPSHOT_COLUMNS = {"status_kind", "status_key", "forecast_kind", "forecast_key"}
COLUMN_TYPES = (
    "select column_name, data_type, character_maximum_length, is_nullable"
    " from information_schema.columns where table_name = 'deal_actions'"
)
CONSTRAINTS = "select conname from pg_constraint where conrelid = 'deal_actions'::regclass"
COUNT_ACTIONS = "select count(*) from deal_actions"
OLD_ACTION_INSERT = (  # M-P1 구조: 스냅숏 컬럼이 없다
    "insert into deal_actions (id, deal_code, action_type, action, memo, next_action, due_date,"
    " acted_at, actor_user_id, created_at, updated_at) values (:id, :deal_code, 'meeting', :action,"
    " :memo, 'n', current_date, now(), :actor, now(), now())"
)
NEW_ACTION_INSERT = (
    "insert into deal_actions (id, deal_code, action_type, action, memo, next_action, due_date,"
    " acted_at, actor_user_id, status_key, forecast_key, created_at, updated_at) values (:id,"
    " :deal_code, 'meeting', :action, :memo, 'n', current_date, now(), :actor, 'prospecting',"
    " 'pipeline', now(), now())"
)


async def _deal_with_an_action(session: AsyncSession, *, insert: str, action: str) -> None:
    actor = await insert_user(session, "kim")
    customer = await insert_contact(session)
    code = await insert_deal(session, customer, actor)
    params = {"id": uuid4(), "deal_code": code, "action": action, "memo": "", "actor": actor}
    await session.execute(text(insert), params)


async def _old_action(session: AsyncSession) -> None:
    await _deal_with_an_action(session, insert=OLD_ACTION_INSERT, action="기존")


async def _long_new_action(session: AsyncSession) -> None:
    await _deal_with_an_action(session, insert=NEW_ACTION_INSERT, action="가" * 5_000)


async def test_upgrade_adds_snapshot_columns_and_constraints(blank_database: URL) -> None:
    """Scenario: 올리면 스냅숏 컬럼 4개와 체크 2개·codes 복합 FK 2개가 생긴다."""
    # Given
    await given_schema_at(blank_database, deal_model_revision())
    assert not SNAPSHOT_COLUMNS & await column_names(blank_database, "deal_actions")
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, action_snapshot_revision())
    assert await column_names(blank_database, "deal_actions") >= SNAPSHOT_COLUMNS
    names = {str(r[0]) for r in await run_sql(blank_database, CONSTRAINTS)}
    assert {
        "ck_deal_actions_status_kind",
        "ck_deal_actions_forecast_kind",
        "fk_deal_actions_status_code",
        "fk_deal_actions_forecast_code",
    } <= names
    fks = await run_sql(
        blank_database,
        "select conname, confdeltype::text, array_length(conkey, 1) from pg_constraint"
        " where conrelid = 'deal_actions'::regclass and confrelid = 'codes'::regclass",
    )
    assert {(r[0], r[1].strip(), r[2]) for r in fks} == {
        ("fk_deal_actions_status_code", "r", 2),
        ("fk_deal_actions_forecast_code", "r", 2),
    }


async def test_upgrade_makes_the_text_columns_unbounded_and_the_plan_fields_required(
    blank_database: URL,
) -> None:
    """Scenario: 올리면 진행사항·Next Action·Memo가 TEXT이고 Next Action·Due Date는 NOT NULL이다."""
    # Given
    await given_schema_at(blank_database, deal_model_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    columns = {r[0]: r for r in await run_sql(blank_database, COLUMN_TYPES)}
    for name in ("action", "next_action", "memo"):
        assert (columns[name][1], columns[name][2]) == ("text", None), name
    for name in ("next_action", "due_date", "status_key", "forecast_key"):
        assert columns[name][3] == "NO", name


async def test_upgrade_discards_the_old_action_rows_because_nothing_is_preserved(
    blank_database: URL,
) -> None:
    """Scenario: 보존 데이터가 없다는 전제라 올리면 기존 Action 행은 삭제되고 Deal은 남는다."""
    # Given
    await given_schema_at(blank_database, deal_model_revision())
    await given_rows(blank_database, _old_action)
    assert await run_sql(blank_database, COUNT_ACTIONS) == [(1,)]
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, COUNT_ACTIONS) == [(0,)]
    assert await run_sql(blank_database, "select count(*) from deals") == [(1,)]


async def test_downgrade_restores_the_exact_structure_of_the_previous_revision(
    blank_database: URL,
) -> None:
    """Scenario: 내리면 deal_actions가 이전 리비전과 열·제약·인덱스까지 같다(VARCHAR, NULL 허용)."""
    # Given
    await given_schema_at(blank_database, deal_model_revision())
    before = await table_structure(blank_database, "deal_actions")
    await when_operator_upgrades(blank_database)
    # When
    await when_operator_downgrades(blank_database, target=deal_model_revision())
    # Then
    await then_schema_is_at(blank_database, deal_model_revision())
    assert await table_structure(blank_database, "deal_actions") == before
    columns = {r[0]: r for r in await run_sql(blank_database, COLUMN_TYPES)}
    assert (columns["action"][1], columns["action"][2]) == ("character varying", 200)
    assert (columns["next_action"][1], columns["next_action"][2]) == ("character varying", 200)
    assert (columns["memo"][1], columns["memo"][2]) == ("character varying", 4000)
    assert (columns["next_action"][3], columns["due_date"][3]) == ("YES", "YES")


async def test_downgrade_clears_the_rows_first_so_long_text_cannot_block_it(
    blank_database: URL,
) -> None:
    """Scenario: 길이 상한 없는 텍스트가 든 행이 있어도 내릴 수 있다(내리기 전에 행을 지운다)."""
    # Given
    await given_schema_at(blank_database, deal_model_revision())
    await when_operator_upgrades(blank_database)
    await given_rows(blank_database, _long_new_action)
    assert await run_sql(blank_database, COUNT_ACTIONS) == [(1,)]
    # When
    await when_operator_downgrades(blank_database, target=deal_model_revision())
    # Then
    await then_schema_is_at(blank_database, deal_model_revision())
    assert await run_sql(blank_database, COUNT_ACTIONS) == [(0,)]


async def test_upgrade_after_downgrade_creates_the_new_structure_again(
    blank_database: URL,
) -> None:
    """Scenario: 내렸다가 다시 올려도 같은 새 구조가 만들어진다."""
    # Given
    await given_schema_at(blank_database, deal_model_revision())
    await when_operator_upgrades(blank_database)
    first = await table_structure(blank_database, "deal_actions")
    await when_operator_downgrades(blank_database, target=deal_model_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, action_snapshot_revision())
    assert await table_structure(blank_database, "deal_actions") == first
