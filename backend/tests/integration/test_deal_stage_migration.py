"""딜 단계 마이그레이션: 기존 행 백필, 구버전 INSERT 호환, CHECK·FK·인덱스, 왕복."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError
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
    customer_id = await _insert_customer(session)
    deal_id = uuid4()
    await _insert_deal(session, customer_id, id=deal_id)
    return str(deal_id)


def _revision_before_deal_stage() -> str:
    """deal_stage_changes 테이블을 만드는 리비전의 직전 리비전."""
    script = ScriptDirectory.from_config(_alembic_config())
    for revision in script.walk_revisions():
        source = Path(revision.path).read_text(encoding="utf-8")
        if "deal_stage_changes" in source and isinstance(revision.down_revision, str):
            return revision.down_revision
    pytest.fail("deal_stage_changes를 만드는 마이그레이션 리비전이 없다")


async def test_existing_style_insert_without_stage_defaults_to_prospecting(
    session: AsyncSession,
) -> None:
    customer_id = await _insert_customer(session)
    deal_id = uuid4()

    await _insert_deal(session, customer_id, id=deal_id)  # stage 열을 모르는 구버전 INSERT

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


async def test_history_has_the_deal_and_time_index(test_database_url: object) -> None:
    engine = create_async_engine(test_database_url, poolclass=NullPool)  # type: ignore[arg-type]
    try:
        async with engine.connect() as connection:
            indexes = await connection.run_sync(
                lambda c: inspect(c).get_indexes("deal_stage_changes")
            )
    finally:
        await engine.dispose()

    by_name = {index["name"]: index["column_names"] for index in indexes}
    assert by_name["ix_deal_stage_changes_deal_id_changed_at"] == ["deal_id", "changed_at"]


async def test_upgrade_fills_existing_deals_with_prospecting() -> None:
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 마이그레이션 백필 테스트를 건너뜁니다")
    before = _revision_before_deal_stage()

    async with temporary_database(admin_url) as url:
        await apply_migrations(url, target=before)
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                session = AsyncSession(bind=connection)
                customer_id = await _insert_customer(session)
                await _insert_deal(session, customer_id, code="OLD-1")
                await _insert_deal(session, customer_id, code="OLD-2")
            await apply_migrations(url)
            async with engine.connect() as connection:
                stages = (await connection.execute(text("select stage from deals"))).scalars().all()
        finally:
            await engine.dispose()

    assert list(stages) == ["prospecting", "prospecting"]
