"""Deal 이력 리비전(HISTORY_REVISION) 스키마: 개명된 컬럼, NULL 허용 계획 필드, 인덱스, RESTRICT FK.

이 리비전까지만 검증한다(이후 리비전은 별도 테스트). 올리기·내리기·데이터 정리 흐름은
tests/functional/schema/test_deal_schema_upgrades.py.
"""

from datetime import date
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.support.legacy_rows import insert_customer, insert_legacy_deal
from tests.support.revisions import HISTORY_REVISION

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMN_INFO = (
    "select column_name, is_nullable, character_maximum_length, data_type"
    " from information_schema.columns where table_name = 'deal_actions'"
)
INSERT_NEW_ACTION = (
    "insert into deal_actions (id, deal_id, action_type, action, memo, next_action, due_date,"
    " acted_at, actor, created_at, updated_at) values (:id, :deal_id, 'meeting', 'a', '',"
    " :next_action, :due_date, now(), '박영업', now(), now())"
)


@pytest.fixture
def test_database_url(database_at: Callable[[str], URL]) -> URL:
    """이 모듈의 DB 테스트는 이력 리비전 스키마에서 돈다(head가 아니다)."""
    return database_at(HISTORY_REVISION)


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
    customer_id = await insert_customer(session)
    deal_id = uuid4()
    await insert_legacy_deal(session, customer_id, id=deal_id)

    await session.execute(
        text(INSERT_NEW_ACTION),
        {"id": uuid4(), "deal_id": deal_id, "next_action": None, "due_date": None},
    )

    count = (await session.execute(text("select count(*) from deal_actions"))).scalar_one()
    assert count == 1


async def test_deal_with_actions_cannot_be_physically_deleted(session: AsyncSession) -> None:
    customer_id = await insert_customer(session)
    deal_id = uuid4()
    await insert_legacy_deal(session, customer_id, id=deal_id)
    await session.execute(
        text(INSERT_NEW_ACTION),
        {"id": uuid4(), "deal_id": deal_id, "next_action": "n", "due_date": date(2026, 3, 10)},
    )

    with pytest.raises(IntegrityError, match="fk_deal_actions_deal_id_deals"):
        await session.execute(text("delete from deals where id = :id"), {"id": deal_id})
