"""Feature: 운영자는 딜 단계·담당자·이력 리비전을 올리고 내려도 기존 딜·활동 데이터가 보존된다.

When: 운영자 명령(alembic upgrade/downgrade). 각 시나리오는 과거 리비전에 행을 넣어 두고
해당 리비전만 적용하므로 이후 리비전이 생겨도 유효하다.
카탈로그 단언은 tests/unit/infra/schema/에 있다.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import text

from tests.functional.steps.schema import (
    column_names,
    given_rows,
    given_schema_at,
    index_names,
    when_operator_downgrades,
    when_operator_upgrades,
)
from tests.support.database import _alembic_config
from tests.support.legacy_rows import insert_customer, insert_legacy_deal
from tests.support.revisions import AUTH_REVISION, HISTORY_REVISION, OWNER_REVISION, STAGE_REVISION
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

INSERT_OLD_ACTION = (
    "insert into deal_actions (id, deal_id, action_type, title, content, acted_at, actor,"
    " created_at, updated_at, deleted_at) values (:id, :deal_id, 'meeting', :title, :content,"
    " now(), '박영업', now(), now(), :deleted_at)"
)
INSERT_NEW_ACTION = (
    "insert into deal_actions (id, deal_id, action_type, action, memo, next_action, due_date,"
    " acted_at, actor, created_at, updated_at) values (:id, :deal_id, 'meeting', 'a', '',"
    " :next_action, :due_date, now(), '박영업', now(), now())"
)
NEW_ACTION_COLUMNS = {"action", "memo", "next_action", "due_date"}


def _revision_before_deal_stage() -> str:
    """deal_stage_changes 테이블을 만드는 리비전(STAGE_REVISION)의 직전 리비전."""
    revision = ScriptDirectory.from_config(_alembic_config()).get_revision(STAGE_REVISION)
    assert revision is not None
    assert isinstance(revision.down_revision, str)
    return revision.down_revision


async def _two_old_deals(session: AsyncSession) -> None:
    customer_id = await insert_customer(session)
    await insert_legacy_deal(session, customer_id, code="OLD-1")
    await insert_legacy_deal(session, customer_id, code="OLD-2")


async def test_operator_upgrade_fills_existing_deals_with_prospecting(
    blank_database: URL,
) -> None:
    """Scenario: 단계 리비전을 올리면 기존 딜의 단계가 모두 prospecting으로 채워진다."""
    # Given
    await given_schema_at(blank_database, _revision_before_deal_stage())
    await given_rows(blank_database, _two_old_deals)
    # When
    await when_operator_upgrades(blank_database, target=STAGE_REVISION)
    # Then
    stages = await run_sql(blank_database, "select stage from deals")
    assert [row[0] for row in stages] == ["prospecting", "prospecting"]


async def test_existing_deals_have_no_owner_user_after_the_owner_upgrade(
    blank_database: URL,
) -> None:
    """Scenario: 담당자 리비전을 올리면 기존 딜의 owner_user_id는 모두 NULL이다."""
    # Given
    await given_schema_at(blank_database, STAGE_REVISION)
    await given_rows(blank_database, _two_old_deals)
    # When
    await when_operator_upgrades(blank_database, target=OWNER_REVISION)
    # Then
    owners = await run_sql(blank_database, "select owner_user_id from deals order by code")
    assert [row[0] for row in owners] == [None, None]


async def test_owner_downgrade_drops_the_column_and_index_but_keeps_deals(
    blank_database: URL,
) -> None:
    """Scenario: 담당자 리비전을 내리면 컬럼·인덱스만 사라지고 딜 행은 남는다."""
    # Given
    await given_schema_at(blank_database, OWNER_REVISION)

    async def seed(session: AsyncSession) -> None:
        customer_id = await insert_customer(session)
        await insert_legacy_deal(session, customer_id, code="KEEP-1")

    await given_rows(blank_database, seed)
    # When
    await when_operator_downgrades(blank_database, target=STAGE_REVISION)
    # Then
    assert "owner_user_id" not in await column_names(blank_database, "deals")
    assert "ix_deals_owner_user_id" not in await index_names(blank_database, "deals")
    assert await run_sql(blank_database, "select code from deals") == [("KEEP-1",)]


async def test_owner_upgrade_after_downgrade_restores_the_column(blank_database: URL) -> None:
    """Scenario: 내렸던 담당자 리비전을 다시 올리면 owner_user_id 컬럼이 돌아온다."""
    # Given
    await given_schema_at(blank_database, OWNER_REVISION)
    await when_operator_downgrades(blank_database, target=STAGE_REVISION)
    # When
    await when_operator_upgrades(blank_database, target=OWNER_REVISION)
    # Then
    assert "owner_user_id" in await column_names(blank_database, "deals")


async def test_history_upgrade_renames_action_columns_and_keeps_data(blank_database: URL) -> None:
    """Scenario: 이력 리비전을 올리면 title/content가 action/memo로 바뀌고 값은 보존된다."""
    # Given
    action_id = uuid4()
    await given_schema_at(blank_database, AUTH_REVISION)

    async def seed(session: AsyncSession) -> None:
        customer_id = await insert_customer(session)
        deal_id = uuid4()
        await insert_legacy_deal(session, customer_id, id=deal_id)
        await session.execute(
            text(INSERT_OLD_ACTION),
            {
                "id": action_id,
                "deal_id": deal_id,
                "title": "킥오프 미팅",
                "content": "요구사항 정리",
                "deleted_at": None,
            },
        )

    await given_rows(blank_database, seed)
    # When
    await when_operator_upgrades(blank_database, target=HISTORY_REVISION)
    # Then
    (row,) = await run_sql(
        blank_database,
        "select action, memo, next_action, due_date, actor from deal_actions where id = :id",
        {"id": action_id},
    )
    assert (row.action, row.memo, row.actor) == ("킥오프 미팅", "요구사항 정리", "박영업")
    assert row.next_action is None
    assert row.due_date is None


async def _seed_actions_with_one_soft_deleted(
    session: AsyncSession, live_id: UUID, gone_id: UUID, orphan_live_id: UUID
) -> None:
    """Deal 둘(하나는 소프트 삭제)과 활동 셋(live, 소프트 삭제된 gone, 삭제된 Deal의 orphan)."""
    customer_id = await insert_customer(session)
    live_deal, deleted_deal = uuid4(), uuid4()
    await insert_legacy_deal(session, customer_id, id=live_deal, code="LIVE")
    await insert_legacy_deal(session, customer_id, id=deleted_deal, code="GONE")
    await session.execute(
        text("update deals set deleted_at = now() where id = :id"), {"id": deleted_deal}
    )
    for action_id, deal_id, deleted_at in (
        (live_id, live_deal, None),
        (gone_id, live_deal, datetime(2026, 1, 1, tzinfo=UTC)),
        (orphan_live_id, deleted_deal, None),
    ):
        await session.execute(
            text(INSERT_OLD_ACTION),
            {
                "id": action_id,
                "deal_id": deal_id,
                "title": "t",
                "content": "c",
                "deleted_at": deleted_at,
            },
        )


async def test_history_upgrade_purges_soft_deleted_actions_only(blank_database: URL) -> None:
    """Scenario: 이력 리비전을 올리면 소프트 삭제된 활동만 지워지고 삭제된 Deal 행은 남는다."""
    # Given
    live_id, gone_id, orphan_live_id = uuid4(), uuid4(), uuid4()
    await given_schema_at(blank_database, AUTH_REVISION)
    await given_rows(
        blank_database,
        lambda session: _seed_actions_with_one_soft_deleted(
            session, live_id, gone_id, orphan_live_id
        ),
    )
    # When
    await when_operator_upgrades(blank_database, target=HISTORY_REVISION)
    # Then
    actions = {row[0] for row in await run_sql(blank_database, "select id from deal_actions")}
    deals = {row[0] for row in await run_sql(blank_database, "select code from deals")}
    assert actions == {live_id, orphan_live_id}  # 소프트 삭제된 활동만 사라진다
    assert deals == {"LIVE", "GONE"}  # 소프트 삭제된 Deal 행은 그대로 둔다


async def _seed_new_style_action(session: AsyncSession, action_id: UUID) -> None:
    customer_id = await insert_customer(session)
    deal_id = uuid4()
    await insert_legacy_deal(session, customer_id, id=deal_id)
    await session.execute(
        text(INSERT_NEW_ACTION),
        {"id": action_id, "deal_id": deal_id, "next_action": "n", "due_date": None},
    )
    await session.execute(
        text("update deal_actions set action = '제안', memo = '내용' where id = :id"),
        {"id": action_id},
    )


async def test_history_downgrade_restores_old_columns_and_values(blank_database: URL) -> None:
    """Scenario: 이력 리비전을 내리면 title/content 컬럼과 값이 복원되고 새 컬럼이 사라진다."""
    # Given
    action_id = uuid4()
    await given_schema_at(blank_database, HISTORY_REVISION)

    async def seed(session: AsyncSession) -> None:
        await _seed_new_style_action(session, action_id)

    await given_rows(blank_database, seed)
    # When
    await when_operator_downgrades(blank_database, target=AUTH_REVISION)
    # Then
    columns = await column_names(blank_database, "deal_actions")
    assert {"title", "content"} <= columns
    assert not (NEW_ACTION_COLUMNS & columns)
    assert "ix_deal_actions_due_date" not in await index_names(blank_database, "deal_actions")
    (old,) = await run_sql(
        blank_database,
        "select title, content from deal_actions where id = :id",
        {"id": action_id},
    )
    assert (old.title, old.content) == ("제안", "내용")


async def test_history_upgrade_after_downgrade_restores_the_new_columns(
    blank_database: URL,
) -> None:
    """Scenario: 내렸던 이력 리비전을 다시 올리면 action/memo/next_action/due_date가 돌아온다."""
    # Given
    await given_schema_at(blank_database, HISTORY_REVISION)

    async def seed(session: AsyncSession) -> None:
        await _seed_new_style_action(session, uuid4())

    await given_rows(blank_database, seed)
    await when_operator_downgrades(blank_database, target=AUTH_REVISION)
    # When
    await when_operator_upgrades(blank_database, target=HISTORY_REVISION)
    # Then
    assert await column_names(blank_database, "deal_actions") >= NEW_ACTION_COLUMNS
