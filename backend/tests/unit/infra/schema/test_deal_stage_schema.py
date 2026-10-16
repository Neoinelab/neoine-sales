"""딜 단계 리비전(STAGE_REVISION) 스키마: 기본값, CHECK, FK, 길이 제한, 인덱스.

올리기 백필은 tests/functional/schema/test_deal_schema_upgrades.py.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.support.legacy_rows import insert_customer, insert_legacy_deal
from tests.support.revisions import STAGE_REVISION

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

INSERT_CHANGE = (
    "insert into deal_stage_changes (id, deal_id, from_stage, to_stage, reason,"
    " changed_by_subject, changed_by_name, changed_at)"
    " values (:id, :deal_id, :from_stage, :to_stage, :reason, 'u', 'n', now())"
)


async def _insert_change(session: AsyncSession, deal_id: str, **overrides: object) -> None:
    values: dict[str, object] = {
        "id": uuid4(),
        "deal_id": deal_id,
        "from_stage": "prospecting",
        "to_stage": "introduction",
        "reason": None,
    }
    values.update(overrides)
    await session.execute(text(INSERT_CHANGE), values)


async def _deal_with_id(session: AsyncSession) -> str:
    customer_id = await insert_customer(session)
    deal_id = uuid4()
    await insert_legacy_deal(session, customer_id, id=deal_id)
    return str(deal_id)


@pytest.fixture
def test_database_url(database_at: Callable[[str], URL]) -> URL:
    """이 모듈의 DB 테스트는 단계 리비전 스키마(changed_by 문자열 컬럼 시절)에서 돈다."""
    return database_at(STAGE_REVISION)


async def test_existing_style_insert_without_stage_defaults_to_prospecting(
    session: AsyncSession,
) -> None:
    customer_id = await insert_customer(session)
    deal_id = uuid4()

    await insert_legacy_deal(session, customer_id, id=deal_id)  # stage 열을 모르는 구버전 INSERT

    stage = (
        await session.execute(text("select stage from deals where id = :id"), {"id": deal_id})
    ).scalar_one()
    assert stage == "prospecting"


async def test_unknown_stage_is_rejected_by_the_database(session: AsyncSession) -> None:
    deal_id = await _deal_with_id(session)

    with pytest.raises(IntegrityError, match="ck_deals_stage_valid"):
        await session.execute(
            text("update deals set stage = 'won' where id = :id"), {"id": deal_id}
        )


async def test_stage_column_is_not_nullable(session: AsyncSession) -> None:
    deal_id = await _deal_with_id(session)

    with pytest.raises(IntegrityError):
        await session.execute(text("update deals set stage = null where id = :id"), {"id": deal_id})


@pytest.mark.parametrize(
    "stage",
    [
        "prospecting",
        "introduction",
        "poc_preparation",
        "poc_completed",
        "technical_evaluation",
        "price_negotiation",
        "contract_completed",
        "lost",
    ],
)
async def test_every_stage_code_is_accepted_by_the_database(
    session: AsyncSession, stage: str
) -> None:
    deal_id = await _deal_with_id(session)

    await session.execute(
        text("update deals set stage = :stage where id = :id"), {"stage": stage, "id": deal_id}
    )


@pytest.mark.parametrize(
    ("column", "constraint"),
    [
        ("from_stage", "ck_deal_stage_changes_from_stage_valid"),
        ("to_stage", "ck_deal_stage_changes_to_stage_valid"),
    ],
)
async def test_history_stage_columns_reject_unknown_values(
    session: AsyncSession, column: str, constraint: str
) -> None:
    deal_id = await _deal_with_id(session)

    with pytest.raises(IntegrityError, match=constraint):
        await _insert_change(session, deal_id, **{column: "won"})


async def test_history_must_reference_an_existing_deal(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="fk_deal_stage_changes_deal_id_deals"):
        await _insert_change(session, str(uuid4()))


async def test_deal_with_history_cannot_be_physically_deleted(session: AsyncSession) -> None:
    deal_id = await _deal_with_id(session)
    await _insert_change(session, deal_id)

    with pytest.raises(IntegrityError, match="fk_deal_stage_changes_deal_id_deals"):
        await session.execute(text("delete from deals where id = :id"), {"id": deal_id})


async def test_history_reason_is_limited_to_500_chars(session: AsyncSession) -> None:
    deal_id = await _deal_with_id(session)
    await _insert_change(session, deal_id, reason="가" * 500)

    with pytest.raises(DBAPIError, match="too long"):
        await _insert_change(session, deal_id, reason="가" * 501)


async def test_history_has_the_deal_and_time_index(test_database_url: URL) -> None:
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            indexes = await connection.run_sync(
                lambda c: inspect(c).get_indexes("deal_stage_changes")
            )
    finally:
        await engine.dispose()

    by_name = {index["name"]: index["column_names"] for index in indexes}
    assert by_name["ix_deal_stage_changes_deal_id_changed_at"] == ["deal_id", "changed_at"]
