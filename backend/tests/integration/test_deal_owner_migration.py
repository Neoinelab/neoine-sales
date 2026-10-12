"""deals.owner_user_id 마이그레이션: NULL 허용 expand, 인덱스, 기존 행 NULL, 구버전 INSERT, 왕복."""

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from alembic.script import Script, ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError
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
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

COLUMN_INFO = (
    "select is_nullable, character_maximum_length, column_default from information_schema.columns"
    " where table_name = 'deals' and column_name = 'owner_user_id'"
)


def _owner_revision() -> Script:
    """deals.owner_user_id를 추가하는 리비전."""
    script = ScriptDirectory.from_config(_alembic_config())
    for revision in script.walk_revisions():
        source = Path(revision.path).read_text(encoding="utf-8")
        if "owner_user_id" in source:
            return revision
    pytest.fail("owner_user_id를 추가하는 마이그레이션 리비전이 없다")


def _stage_revision_id() -> str:
    script = ScriptDirectory.from_config(_alembic_config())
    for revision in script.walk_revisions():
        if "deal_stage_changes" in Path(revision.path).read_text(encoding="utf-8"):
            return revision.revision
    pytest.fail("deal_stage_changes를 만드는 마이그레이션 리비전이 없다")


def _previous_revision() -> str:
    previous = _owner_revision().down_revision
    assert isinstance(previous, str)
    return previous


def test_owner_revision_follows_the_stage_revision_and_is_in_the_single_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    assert _owner_revision().down_revision == _stage_revision_id()
    heads = script.get_heads()
    assert len(heads) == 1
    history = {revision.revision for revision in script.iterate_revisions(heads[0], "base")}
    assert _owner_revision().revision in history


async def test_owner_user_id_column_is_nullable_text_without_default(
    session: AsyncSession,
) -> None:
    row = (await session.execute(text(COLUMN_INFO))).one()

    assert row.is_nullable == "YES"
    assert row.character_maximum_length == 200
    assert row.column_default is None


async def test_owner_user_id_has_an_index(test_database_url: URL) -> None:
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            indexes = await connection.run_sync(lambda c: inspect(c).get_indexes("deals"))
    finally:
        await engine.dispose()

    by_name = {index["name"]: index["column_names"] for index in indexes}
    assert by_name["ix_deals_owner_user_id"] == ["owner_user_id"]


async def test_existing_style_insert_without_owner_user_id_is_null(session: AsyncSession) -> None:
    customer_id = await _insert_customer(session)
    deal_id = uuid4()

    await _insert_deal(session, customer_id, id=deal_id)  # owner_user_id 열을 모르는 구버전 INSERT

    owner = (
        await session.execute(
            text("select owner_user_id from deals where id = :id"), {"id": deal_id}
        )
    ).scalar_one()
    assert owner is None


async def test_owner_user_id_is_limited_to_200_chars(session: AsyncSession) -> None:
    customer_id = await _insert_customer(session)
    deal_id = uuid4()
    await _insert_deal(session, customer_id, id=deal_id)

    await session.execute(
        text("update deals set owner_user_id = :v where id = :id"), {"v": "u" * 200, "id": deal_id}
    )
    with pytest.raises(DBAPIError, match="too long"):
        await session.execute(
            text("update deals set owner_user_id = :v where id = :id"),
            {"v": "u" * 201, "id": deal_id},
        )


async def test_existing_deals_have_no_owner_user_after_upgrade() -> None:
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 마이그레이션 테스트를 건너뜁니다")

    async with temporary_database(admin_url) as url:
        await apply_migrations(url, target=_previous_revision())
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                session = AsyncSession(bind=connection)
                customer_id = await _insert_customer(session)
                await _insert_deal(session, customer_id, code="OLD-1")
                await _insert_deal(session, customer_id, code="OLD-2")
            await apply_migrations(url)
            async with engine.connect() as connection:
                owners = (
                    (
                        await connection.execute(
                            text("select owner_user_id from deals order by code")
                        )
                    )
                    .scalars()
                    .all()
                )
        finally:
            await engine.dispose()

    assert list(owners) == [None, None]


async def test_downgrade_drops_the_column_and_index_but_keeps_deals() -> None:
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 마이그레이션 왕복 테스트를 건너뜁니다")

    async with temporary_database(admin_url) as url:
        await apply_migrations(url)
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                session = AsyncSession(bind=connection)
                customer_id = await _insert_customer(session)
                await _insert_deal(session, customer_id, code="KEEP-1")
            await apply_migrations(url, direction="down", target=_previous_revision())
            async with engine.connect() as connection:
                columns = await connection.run_sync(
                    lambda c: {col["name"] for col in inspect(c).get_columns("deals")}
                )
                indexes = await connection.run_sync(
                    lambda c: {i["name"] for i in inspect(c).get_indexes("deals")}
                )
                codes = (await connection.execute(text("select code from deals"))).scalars().all()
            await apply_migrations(url)
            async with engine.connect() as connection:
                again = await connection.run_sync(
                    lambda c: {col["name"] for col in inspect(c).get_columns("deals")}
                )
        finally:
            await engine.dispose()

    assert "owner_user_id" not in columns
    assert "ix_deals_owner_user_id" not in indexes
    assert list(codes) == ["KEEP-1"]
    assert "owner_user_id" in again
