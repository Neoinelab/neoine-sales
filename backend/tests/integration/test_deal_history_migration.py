"""Deal 이력 마이그레이션(단일 리비전): 개명·신규 컬럼·소프트 삭제 활동 정리.

계획(AC10, 7절): 데이터 보존 rename, next_action/due_date는 NULL 허용(백필 없음), 인덱스 추가,
소프트 삭제된 활동 행만 삭제(소프트 삭제된 Deal 행은 유지), 두 FK는 RESTRICT 유지, 왕복 가능.
"""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from alembic.script import Script, ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from tests.integration.test_migrations import _insert_customer, _insert_deal
from tests.support.database import (
    _alembic_config,
    apply_migrations,
    resolve_admin_url,
    temporary_database,
)
from tests.support.skips import skip_or_fail

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

PREVIOUS_HEAD = "dd7f21f7190e"

COLUMN_INFO = (
    "select column_name, is_nullable, character_maximum_length, data_type"
    " from information_schema.columns where table_name = 'deal_actions'"
)
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


def _history_revision() -> Script:
    """deal_actions.next_action을 추가하는 리비전."""
    script = ScriptDirectory.from_config(_alembic_config())
    for revision in script.walk_revisions():
        source = Path(revision.path).read_text(encoding="utf-8")
        if "next_action" in source and "deal_actions" in source:
            return revision
    pytest.fail("deal_actions.next_action을 추가하는 마이그레이션 리비전이 없다")


def test_history_revision_follows_the_previous_head_and_is_the_single_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    revision = _history_revision()

    assert revision.down_revision == PREVIOUS_HEAD
    assert script.get_heads() == [revision.revision]


async def test_columns_are_renamed_and_new_ones_are_nullable(test_database_url: URL) -> None:
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            rows = (await connection.execute(text(COLUMN_INFO))).all()
    finally:
        await engine.dispose()
    columns = {r.column_name: r for r in rows}

    assert "title" not in columns
    assert "content" not in columns
    assert (columns["action"].is_nullable, columns["action"].character_maximum_length) == (
        "NO",
        200,
    )
    assert (columns["memo"].is_nullable, columns["memo"].character_maximum_length) == ("NO", 4000)
    assert (
        columns["next_action"].is_nullable,
        columns["next_action"].character_maximum_length,
    ) == (
        "YES",
        200,
    )
    assert (columns["due_date"].is_nullable, columns["due_date"].data_type) == ("YES", "date")


async def test_due_date_index_exists_and_deal_fks_stay_restrict(test_database_url: URL) -> None:
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            indexes = await connection.run_sync(
                lambda c: {i["name"] for i in inspect(c).get_indexes("deal_actions")}
            )
            delete_rules: dict[str, str] = dict(
                (
                    await connection.execute(
                        text(
                            "select conname, confdeltype::text from pg_constraint where conname in"
                            " ('fk_deal_actions_deal_id_deals',"
                            " 'fk_deal_stage_changes_deal_id_deals')"
                        )
                    )
                ).all()
            )
    finally:
        await engine.dispose()

    assert {"ix_deal_actions_due_date", "ix_deal_actions_acted_at"} <= indexes
    assert "ix_deal_actions_deal_id_acted_at" in indexes
    assert delete_rules == {
        "fk_deal_actions_deal_id_deals": "r",
        "fk_deal_stage_changes_deal_id_deals": "r",
    }


async def test_new_style_rows_accept_null_plan_fields(session: AsyncSession) -> None:
    customer_id = await _insert_customer(session)
    deal_id = uuid4()
    await _insert_deal(session, customer_id, id=deal_id)

    await session.execute(
        text(INSERT_NEW_ACTION),
        {"id": uuid4(), "deal_id": deal_id, "next_action": None, "due_date": None},
    )

    count = (await session.execute(text("select count(*) from deal_actions"))).scalar_one()
    assert count == 1


async def test_deal_with_actions_cannot_be_physically_deleted(session: AsyncSession) -> None:
    customer_id = await _insert_customer(session)
    deal_id = uuid4()
    await _insert_deal(session, customer_id, id=deal_id)
    await session.execute(
        text(INSERT_NEW_ACTION),
        {"id": uuid4(), "deal_id": deal_id, "next_action": "n", "due_date": date(2026, 3, 10)},
    )

    with pytest.raises(IntegrityError, match="fk_deal_actions_deal_id_deals"):
        await session.execute(text("delete from deals where id = :id"), {"id": deal_id})


async def test_migration_renames_columns_and_keeps_data() -> None:
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 마이그레이션 테스트를 건너뜁니다")
    action_id = uuid4()

    async with temporary_database(admin_url) as url:
        await apply_migrations(url, target=PREVIOUS_HEAD)
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                session = AsyncSession(bind=connection)
                customer_id = await _insert_customer(session)
                deal_id = uuid4()
                await _insert_deal(session, customer_id, id=deal_id)
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
            await apply_migrations(url)
            async with engine.connect() as connection:
                row = (
                    await connection.execute(
                        text(
                            "select action, memo, next_action, due_date, actor"
                            " from deal_actions where id = :id"
                        ),
                        {"id": action_id},
                    )
                ).one()
        finally:
            await engine.dispose()

    assert (row.action, row.memo, row.actor) == ("킥오프 미팅", "요구사항 정리", "박영업")
    assert row.next_action is None
    assert row.due_date is None


async def test_migration_purges_soft_deleted_actions_only() -> None:
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 마이그레이션 테스트를 건너뜁니다")
    live_id, gone_id, orphan_live_id = uuid4(), uuid4(), uuid4()

    async with temporary_database(admin_url) as url:
        await apply_migrations(url, target=PREVIOUS_HEAD)
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                session = AsyncSession(bind=connection)
                customer_id = await _insert_customer(session)
                live_deal, deleted_deal = uuid4(), uuid4()
                await _insert_deal(session, customer_id, id=live_deal, code="LIVE")
                await _insert_deal(session, customer_id, id=deleted_deal, code="GONE")
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
            await apply_migrations(url)
            async with engine.connect() as connection:
                actions = set(
                    (await connection.execute(text("select id from deal_actions"))).scalars()
                )
                deals = set((await connection.execute(text("select code from deals"))).scalars())
        finally:
            await engine.dispose()

    assert actions == {live_id, orphan_live_id}  # 소프트 삭제된 활동만 사라진다
    assert deals == {"LIVE", "GONE"}  # 소프트 삭제된 Deal 행은 그대로 둔다


async def _seed_new_style_action(session: AsyncSession, action_id: UUID) -> None:
    customer_id = await _insert_customer(session)
    deal_id = uuid4()
    await _insert_deal(session, customer_id, id=deal_id)
    await session.execute(
        text(INSERT_NEW_ACTION),
        {"id": action_id, "deal_id": deal_id, "next_action": "n", "due_date": None},
    )
    await session.execute(
        text("update deal_actions set action = '제안', memo = '내용' where id = :id"),
        {"id": action_id},
    )


async def test_downgrade_restores_old_columns_and_upgrade_again_works() -> None:
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 마이그레이션 왕복 테스트를 건너뜁니다")
    action_id = uuid4()

    async with temporary_database(admin_url) as url:
        await apply_migrations(url)
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                await _seed_new_style_action(AsyncSession(bind=connection), action_id)
            await apply_migrations(url, direction="down", target=PREVIOUS_HEAD)
            async with engine.connect() as connection:
                columns = await connection.run_sync(
                    lambda c: {col["name"] for col in inspect(c).get_columns("deal_actions")}
                )
                indexes = await connection.run_sync(
                    lambda c: {i["name"] for i in inspect(c).get_indexes("deal_actions")}
                )
                old = (
                    await connection.execute(
                        text("select title, content from deal_actions where id = :id"),
                        {"id": action_id},
                    )
                ).one()
            await apply_migrations(url)
            async with engine.connect() as connection:
                again = await connection.run_sync(
                    lambda c: {col["name"] for col in inspect(c).get_columns("deal_actions")}
                )
        finally:
            await engine.dispose()

    assert {"title", "content"} <= columns
    assert not ({"action", "memo", "next_action", "due_date"} & columns)
    assert "ix_deal_actions_due_date" not in indexes
    assert (old.title, old.content) == ("제안", "내용")
    assert {"action", "memo", "next_action", "due_date"} <= again
