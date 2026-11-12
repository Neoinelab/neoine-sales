"""head 스키마의 deal_bant_labels: 구분당 1개, 구분이 맞는 Label만(복합 FK)."""

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
    """deal_bant_labels의 열·기본 키·인덱스가 기대와 같은지 확인한다."""
    # when: 열, 기본 키, 인덱스 정보를 조회한다 (전제: head 스키마 DB 세션)
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

    # then: 열 3개, (deal_id, category) 기본 키, label_id 인덱스가 있다
    assert columns == COLUMNS
    assert primary_key == {"deal_id", "category"}
    assert "ix_deal_bant_labels_label_id" in indexes


async def test_foreign_keys_cascade_from_the_deal_and_restrict_the_label_pair(
    session: AsyncSession,
) -> None:
    """Deal FK는 CASCADE, Label 쌍 FK는 RESTRICT인지 확인한다."""
    # when: deal_bant_labels의 FK와 Label 유니크 제약을 조회한다 (전제: head 스키마 DB 세션)
    rows = (await session.execute(text(FOREIGN_KEYS))).all()

    # then: Deal은 CASCADE, Label은 RESTRICT 2열 FK이고 (id, category) 유니크가 있다
    assert {(r[0], r[1], r[2].strip(), r[3]) for r in rows} == {
        ("fk_deal_bant_labels_deal_id_deals", "deals", "c", 1),
        ("fk_deal_bant_labels_label", "bant_labels", "r", 2),
    }
    assert (await session.execute(text(LABEL_UNIQUE))).scalar_one() == "uq_bant_labels_id_category"


async def test_one_label_per_category_per_deal(session: AsyncSession) -> None:
    """Deal당 구분마다 Label이 하나만 허용되는지 확인한다."""
    # given: 한 구분에 Label이 이미 선택된 Deal이 있다
    code = await _deal(session)
    await insert_bant(session, code, "budget", await _label(session, "budget", "풀 예산 확보"))

    # when·then: 같은 구분에 다른 Label을 또 넣으면 기본 키 위반이 난다
    with pytest.raises(IntegrityError, match="pk_deal_bant_labels"):
        await insert_bant(session, code, "budget", await _label(session, "budget", "미확인"))


async def test_one_label_in_each_of_the_four_categories_is_allowed(session: AsyncSession) -> None:
    """네 구분에 Label을 하나씩 넣을 수 있는지 확인한다."""
    # given: Deal이 있다
    code = await _deal(session)

    # when·then: 네 구분에 각각 Label을 넣어도 오류가 나지 않는다
    for category, name in (
        ("budget", "풀 예산 확보"),
        ("authority", "CEO 보고 완료"),
        ("need", "CISO 지시"),
        ("timeline", "금년 구매"),
    ):
        await insert_bant(session, code, category, await _label(session, category, name))


async def test_a_label_of_another_category_is_rejected(session: AsyncSession) -> None:
    """다른 구분의 Label은 DB가 거절하는지 확인한다."""
    # given: Deal과 need 구분 Label이 있다
    code = await _deal(session)
    need_label = await _label(session, "need", "모름")

    # when·then: need Label을 budget 구분에 넣으면 Label FK 위반이 난다
    with pytest.raises(IntegrityError, match="fk_deal_bant_labels_label"):
        await insert_bant(session, code, "budget", need_label)


async def test_an_unknown_category_is_rejected(session: AsyncSession) -> None:
    """알 수 없는 구분은 DB가 거절하는지 확인한다."""
    # given: Deal이 있다
    code = await _deal(session)

    # when·then: 없는 구분으로 넣으면 무결성 오류가 난다
    with pytest.raises(IntegrityError):
        await insert_bant(session, code, "scale", await _label(session, "budget", "미확인"))


async def test_a_label_in_use_cannot_be_deleted(session: AsyncSession) -> None:
    """선택에 쓰이는 Label은 삭제할 수 없는지 확인한다."""
    # given: Label이 선택된 Deal이 있다
    code = await _deal(session)
    label = await _label(session, "budget", "예산 없음")
    await insert_bant(session, code, "budget", label)

    # when·then: 그 Label을 삭제하면 Label FK 위반이 난다
    with pytest.raises(IntegrityError, match="fk_deal_bant_labels_label"):
        await session.execute(text("delete from bant_labels where id = :id"), {"id": label})


async def test_deleting_the_deal_deletes_its_selections_but_keeps_the_label(
    session: AsyncSession,
) -> None:
    """Deal을 지우면 선택은 지워지고 Label은 남는지 확인한다."""
    # given: Label이 선택된 Deal이 있다
    code = await _deal(session)
    label = await _label(session, "budget", "예산 없음")
    await insert_bant(session, code, "budget", label)

    # when: Deal을 삭제한다 (전제: head 스키마 DB 세션)
    await session.execute(text("delete from deals where deal_code = :code"), {"code": code})

    # then: 선택은 0건이고 Label은 1건 남는다
    selections = (await session.execute(text("select count(*) from deal_bant_labels"))).scalar_one()
    labels = (
        await session.execute(
            text("select count(*) from bant_labels where id = :id"), {"id": label}
        )
    ).scalar_one()
    assert (selections, labels) == (0, 1)
