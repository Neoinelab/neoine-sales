"""head 스키마의 deal_bant_labels(AC-13·14·28): 구분당 1개, 구분이 맞는 Label만(복합 FK)."""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.head_rows import insert_bant, insert_contact, insert_deal

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMNS = {"deal_id", "category", "label_id"}
LABEL_BY_NAME = "select id from bant_labels where category = :category and name = :name"
PRIMARY_KEY = (
    "select a.attname from pg_constraint c join pg_attribute a"
    " on a.attrelid = c.conrelid and a.attnum = any(c.conkey)"
    " where c.conrelid = 'deal_bant_labels'::regclass and c.contype = 'p'"
)
FOREIGN_KEYS = (
    "select conname, confrelid::regclass::text, confdeltype::text, array_length(conkey, 1)"
    " from pg_constraint where conrelid = 'deal_bant_labels'::regclass and contype = 'f'"
)
LABEL_UNIQUE = (
    "select conname from pg_constraint"
    " where conrelid = 'bant_labels'::regclass and contype = 'u'"
    " and conname = 'uq_bant_labels_id_category'"
)


async def _label(session: AsyncSession, category: str, name: str) -> int:
    return int(
        (
            await session.execute(text(LABEL_BY_NAME), {"category": category, "name": name})
        ).scalar_one()
    )


async def _deal(session: AsyncSession) -> str:
    return await insert_deal(session, await insert_contact(session))


async def test_the_table_has_the_expected_shape(session: AsyncSession) -> None:
    columns = {
        r[0]
        for r in (
            await session.execute(
                text(
                    "select column_name from information_schema.columns"
                    " where table_name = 'deal_bant_labels'"
                )
            )
        ).all()
    }
    primary_key = {r[0] for r in (await session.execute(text(PRIMARY_KEY))).all()}
    indexes = {
        r[0]
        for r in (
            await session.execute(
                text("select indexname from pg_indexes where tablename = 'deal_bant_labels'")
            )
        ).all()
    }

    assert columns == COLUMNS
    assert primary_key == {"deal_id", "category"}
    assert "ix_deal_bant_labels_label_id" in indexes


async def test_foreign_keys_cascade_from_the_deal_and_restrict_the_label_pair(
    session: AsyncSession,
) -> None:
    rows = (await session.execute(text(FOREIGN_KEYS))).all()

    assert {(r[0], r[1], r[2].strip(), r[3]) for r in rows} == {
        ("fk_deal_bant_labels_deal_id_deals", "deals", "c", 1),
        ("fk_deal_bant_labels_label", "bant_labels", "r", 2),
    }
    assert (await session.execute(text(LABEL_UNIQUE))).scalar_one() == "uq_bant_labels_id_category"


async def test_one_label_per_category_per_deal(session: AsyncSession) -> None:
    code = await _deal(session)
    await insert_bant(session, code, "budget", await _label(session, "budget", "풀 예산 확보"))

    with pytest.raises(IntegrityError, match="pk_deal_bant_labels"):
        await insert_bant(session, code, "budget", await _label(session, "budget", "미확인"))


async def test_one_label_in_each_of_the_four_categories_is_allowed(session: AsyncSession) -> None:
    code = await _deal(session)

    for category, name in (
        ("budget", "풀 예산 확보"),
        ("authority", "CEO 보고 완료"),
        ("need", "CISO 지시"),
        ("timeline", "금년 구매"),
    ):
        await insert_bant(session, code, category, await _label(session, category, name))


async def test_a_label_of_another_category_is_rejected(session: AsyncSession) -> None:
    code = await _deal(session)
    need_label = await _label(session, "need", "모름")

    with pytest.raises(IntegrityError, match="fk_deal_bant_labels_label"):
        await insert_bant(session, code, "budget", need_label)


async def test_an_unknown_category_is_rejected(session: AsyncSession) -> None:
    code = await _deal(session)

    with pytest.raises(IntegrityError):
        await insert_bant(session, code, "scale", await _label(session, "budget", "미확인"))


async def test_a_label_in_use_cannot_be_deleted(session: AsyncSession) -> None:
    code = await _deal(session)
    label = await _label(session, "budget", "예산 없음")
    await insert_bant(session, code, "budget", label)

    with pytest.raises(IntegrityError, match="fk_deal_bant_labels_label"):
        await session.execute(text("delete from bant_labels where id = :id"), {"id": label})


async def test_deleting_the_deal_deletes_its_selections_but_keeps_the_label(
    session: AsyncSession,
) -> None:
    code = await _deal(session)
    label = await _label(session, "budget", "예산 없음")
    await insert_bant(session, code, "budget", label)

    await session.execute(text("delete from deals where deal_code = :code"), {"code": code})

    selections = (await session.execute(text("select count(*) from deal_bant_labels"))).scalar_one()
    labels = (
        await session.execute(
            text("select count(*) from bant_labels where id = :id"), {"id": label}
        )
    ).scalar_one()
    assert (selections, labels) == (0, 1)
