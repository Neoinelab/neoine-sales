"""Feature: 운영자는 첨부 파일 리비전(M-P2b)을 올리고 내려 저장 위치·첨부 테이블을 만들고 지운다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 Action 스냅숏 리비전(M-P2) 다음이다.
순수 expand라 올려도 기존 테이블과 행은 바뀌지 않는다. 내리면 두 테이블만 사라진다(디스크 파일은
다루지 않는다).
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
)
from tests.functional.steps.schema import when_operator_upgrades as upgrade_database
from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.revisions import action_snapshot_revision, attachments_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

NEW_TABLES = {"storage_settings", "deal_attachments"}
EXISTING_TABLES_TO_KEEP = ("users", "deals", "deal_actions", "deal_history", "directory_settings")


async def when_operator_upgrades(url: URL) -> None:
    """운영자 명령: M-P2b 리비전까지 올린다(head는 이후 리비전으로 앞서갈 수 있다)."""
    await upgrade_database(url, target=attachments_revision())


async def _deal_with_an_owner(session: AsyncSession) -> None:
    owner = await insert_user(session, "kim")
    await insert_deal(session, await insert_contact(session), owner)


async def test_upgrade_creates_the_attachment_tables(blank_database: URL) -> None:
    """Scenario: 올리면 storage_settings와 deal_attachments가 생긴다."""
    # Given
    await given_schema_at(blank_database, action_snapshot_revision())
    assert not NEW_TABLES & await table_names(blank_database)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, attachments_revision())
    assert await table_names(blank_database) >= NEW_TABLES


async def test_upgrade_leaves_the_existing_tables_and_rows_unchanged(blank_database: URL) -> None:
    """Scenario: 순수 expand라 올려도 기존 테이블의 구조와 행이 그대로다(구 앱과 호환)."""
    # Given
    await given_schema_at(blank_database, action_snapshot_revision())
    await given_rows(blank_database, _deal_with_an_owner)
    before = {name: await table_structure(blank_database, name) for name in EXISTING_TABLES_TO_KEEP}
    # When
    await when_operator_upgrades(blank_database)
    # Then
    after = {name: await table_structure(blank_database, name) for name in EXISTING_TABLES_TO_KEEP}
    assert after == before
    assert await run_sql(blank_database, "select count(*) from deals") == [(1,)]
    assert await run_sql(blank_database, "select count(*) from users") == [(1,)]


async def test_upgrade_starts_with_empty_attachment_tables(blank_database: URL) -> None:
    """Scenario: 새 테이블에는 행이 없다(저장 위치는 최초 설정·외부연동에서 등록한다)."""
    # Given
    await given_schema_at(blank_database, action_snapshot_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select count(*) from storage_settings") == [(0,)]
    assert await run_sql(blank_database, "select count(*) from deal_attachments") == [(0,)]


async def test_downgrade_drops_the_attachment_tables(blank_database: URL) -> None:
    """Scenario: 내리면 두 테이블이 지워지고 이전 리비전 스키마로 돌아간다."""
    # Given
    await given_schema_at(blank_database, action_snapshot_revision())
    await when_operator_upgrades(blank_database)
    # When
    await when_operator_downgrades(blank_database, target=action_snapshot_revision())
    # Then
    await then_schema_is_at(blank_database, action_snapshot_revision())
    assert not NEW_TABLES & await table_names(blank_database)


async def test_downgrade_keeps_the_other_tables_and_their_rows(blank_database: URL) -> None:
    """Scenario: 내려도 Deal·사용자 같은 기존 데이터는 그대로다."""
    # Given
    await given_schema_at(blank_database, action_snapshot_revision())
    await when_operator_upgrades(blank_database)
    await given_rows(blank_database, _deal_with_an_owner)
    # When
    await when_operator_downgrades(blank_database, target=action_snapshot_revision())
    # Then
    assert await run_sql(blank_database, "select count(*) from deals") == [(1,)]
    assert await run_sql(blank_database, "select count(*) from users") == [(1,)]


async def test_upgrade_after_downgrade_creates_the_same_tables_again(blank_database: URL) -> None:
    """Scenario: 내렸다가 다시 올려도 같은 구조의 테이블이 만들어진다."""
    # Given
    await given_schema_at(blank_database, action_snapshot_revision())
    await when_operator_upgrades(blank_database)
    first = {name: await table_structure(blank_database, name) for name in NEW_TABLES}
    await when_operator_downgrades(blank_database, target=action_snapshot_revision())
    # When
    await when_operator_upgrades(blank_database)
    # Then
    second = {name: await table_structure(blank_database, name) for name in NEW_TABLES}
    assert second == first
    await then_schema_is_at(blank_database, attachments_revision())
