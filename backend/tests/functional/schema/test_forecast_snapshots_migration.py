"""Feature: 운영자는 Forecast 스냅숏 리비전(M-R2)을 올리고 내려 세 테이블을 둔다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 BIGINT id 리비전(`a3f7c1d95b28`) 바로
다음이고 head다. `forecast_snapshots`·`forecast_snapshot_columns`(저장 당시 Forecast 코드 목록)·
`forecast_snapshot_cells` 세 테이블만 추가하는 순수 expand라 기존 테이블 구조와 행은 그대로이고
(구 앱과 같은 DB에서 공존 가능), 시드 행도 없다. 내리면 세 테이블만 사라진다(스냅숏 데이터 소실은
개발 단계라 허용).
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.schema import (
    given_rows,
    given_schema_at,
    table_names,
    table_structure,
    then_schema_is_at,
    when_operator_downgrades,
    when_operator_upgrades,
)
from tests.support.head_rows import insert_user
from tests.support.revisions import bigint_ids_revision, forecast_snapshots_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

NEW_TABLES = {"forecast_snapshots", "forecast_snapshot_columns", "forecast_snapshot_cells"}
EXISTING_TABLES = ("users", "deals", "codes", "deal_actions", "action_types")


async def _one_user(session: AsyncSession) -> None:
    await insert_user(session, "kim")


async def test_upgrade_creates_the_three_tables_and_nothing_else_changes(
    blank_database: URL,
) -> None:
    """Scenario: 올리면 세 테이블만 생기고 기존 테이블 구조는 그대로이며 행도 남는다."""
    # Given
    await given_schema_at(blank_database, bigint_ids_revision())
    await given_rows(blank_database, _one_user)
    before_tables = await table_names(blank_database)
    before = {name: await table_structure(blank_database, name) for name in EXISTING_TABLES}
    assert not NEW_TABLES & before_tables
    # When
    await when_operator_upgrades(blank_database, target=forecast_snapshots_revision())
    # Then
    await then_schema_is_at(blank_database, forecast_snapshots_revision())
    assert await table_names(blank_database) == before_tables | NEW_TABLES
    after = {name: await table_structure(blank_database, name) for name in EXISTING_TABLES}
    assert after == before
    assert await run_sql(blank_database, "select count(*) from users") == [(1,)]


async def test_upgrade_seeds_no_snapshot_rows(blank_database: URL) -> None:
    """Scenario: 새 테이블은 비어 있다(스냅숏은 Batch가 만든다)."""
    # Given
    await given_schema_at(blank_database, bigint_ids_revision())
    # When
    await when_operator_upgrades(blank_database, target=forecast_snapshots_revision())
    # Then
    assert await run_sql(blank_database, "select count(*) from forecast_snapshots") == [(0,)]
    assert await run_sql(blank_database, "select count(*) from forecast_snapshot_columns") == [(0,)]
    assert await run_sql(blank_database, "select count(*) from forecast_snapshot_cells") == [(0,)]


async def test_upgrade_to_head_ends_at_the_snapshot_revision(blank_database: URL) -> None:
    """Scenario: 빈 DB를 head로 올리면 이 리비전에 이른다(head는 이 리비전이다)."""
    # Given
    # (마이그레이션이 하나도 적용되지 않은 빈 DB)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, forecast_snapshots_revision())
    assert (await table_names(blank_database)) >= NEW_TABLES


async def test_downgrade_drops_only_the_three_tables(blank_database: URL) -> None:
    """Scenario: 내리면 세 테이블이 사라지고 기존 테이블 구조와 행은 올리기 전과 같다."""
    # Given
    await given_schema_at(blank_database, bigint_ids_revision())
    await given_rows(blank_database, _one_user)
    before_tables = await table_names(blank_database)
    before = {name: await table_structure(blank_database, name) for name in EXISTING_TABLES}
    await when_operator_upgrades(blank_database, target=forecast_snapshots_revision())
    # When
    await when_operator_downgrades(blank_database, target=bigint_ids_revision())
    # Then
    await then_schema_is_at(blank_database, bigint_ids_revision())
    assert await table_names(blank_database) == before_tables
    assert {name: await table_structure(blank_database, name) for name in EXISTING_TABLES} == before
    assert await run_sql(blank_database, "select count(*) from users") == [(1,)]


async def test_downgrade_removes_snapshot_data_with_the_tables(blank_database: URL) -> None:
    """Scenario: 스냅숏이 쌓인 DB도 내리면 세 테이블이 사라진다(스냅숏 소실은 허용된 동작)."""
    # Given
    await given_schema_at(blank_database, forecast_snapshots_revision())

    async def one_snapshot(session: AsyncSession) -> None:
        from tests.support.forecast_rows import (  # noqa: PLC0415
            insert_cell,
            insert_column,
            insert_snapshot,
        )

        owner = await insert_user(session, "lee")
        snapshot = await insert_snapshot(session)
        await insert_column(session, snapshot)
        await insert_cell(session, snapshot, owner)

    await given_rows(blank_database, one_snapshot)
    # When
    await when_operator_downgrades(blank_database, target=bigint_ids_revision())
    # Then
    assert not NEW_TABLES & await table_names(blank_database)


async def test_upgrade_after_downgrade_creates_the_same_structure_again(
    blank_database: URL,
) -> None:
    """Scenario: 내렸다가 다시 올려도 세 테이블 구조(열·제약·인덱스 이름까지)가 같다."""
    # Given
    await given_schema_at(blank_database, forecast_snapshots_revision())
    first = {name: await table_structure(blank_database, name) for name in sorted(NEW_TABLES)}
    await when_operator_downgrades(blank_database, target=bigint_ids_revision())
    # When
    await when_operator_upgrades(blank_database, target=forecast_snapshots_revision())
    # Then
    second = {name: await table_structure(blank_database, name) for name in sorted(NEW_TABLES)}
    assert second == first
    assert all(first[name]["columns"] for name in first)
    await then_schema_is_at(blank_database, forecast_snapshots_revision())
