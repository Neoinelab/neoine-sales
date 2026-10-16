"""BANT Label 참조 위반의 오류 문구 계약(R2 리뷰 이월 4): 내부 repr을 응답으로 내보내지 않는다.

Fake와 SQL(PostgreSQL)에 같은 기대값. 없는 Label이거나 다른 구분의 Label을 가리키면
InvalidReferenceError이고, 문구는 어떤 항목이 문제인지만 말한다(`BantSelection(...)`·`UUID(...)`
같은 객체 표현이 들어가면 안 된다). 오류 뒤에도 같은 트랜잭션을 계속 쓸 수 있다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.common.errors import InvalidReferenceError
from tests.factories import later, make_bant, make_deal

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"
FORBIDDEN = ("BantSelection", "UUID(", "budget=", "authority=")


def _assert_clean(error: InvalidReferenceError) -> None:
    message = str(error)
    assert "BANT Label" in message
    for fragment in FORBIDDEN:
        assert fragment not in message, message


async def test_adding_with_an_unknown_label_is_an_invalid_reference_without_object_reprs(
    deal_case: DealCase,
) -> None:
    deal = make_deal(code=CODE, bant=make_bant(budget=BantLabelId(uuid4())))

    with pytest.raises(InvalidReferenceError) as raised:
        await deal_case.add(deal)

    _assert_clean(raised.value)
    assert await deal_case.deals.exists(deal.id) is False


async def test_adding_with_a_label_of_another_category_is_an_invalid_reference(
    deal_case: DealCase,
) -> None:
    need = await deal_case.new_label(BantCategory.NEED, "필요 가")
    deal = make_deal(code=CODE, bant=make_bant(budget=need.id))  # 필요 Label을 예산에 선택

    with pytest.raises(InvalidReferenceError) as raised:
        await deal_case.add(deal)

    _assert_clean(raised.value)


async def test_updating_to_an_unknown_label_is_an_invalid_reference_and_keeps_the_old_one(
    deal_case: DealCase,
) -> None:
    budget = await deal_case.new_label(BantCategory.BUDGET, "예산 가")
    deal = make_deal(later(1), code=CODE, bant=make_bant(budget=budget.id))
    await deal_case.add(deal)

    with pytest.raises(InvalidReferenceError) as raised:
        await deal_case.revise(deal.id, bant=make_bant(budget=BantLabelId(uuid4())))

    _assert_clean(raised.value)
    assert (await deal_case.deals.get(deal.id)).bant == make_bant(budget=budget.id)


async def test_the_transaction_stays_usable_after_the_invalid_reference(
    deal_case: DealCase,
) -> None:
    with pytest.raises(InvalidReferenceError):
        await deal_case.add(make_deal(code=CODE, bant=make_bant(need=BantLabelId(uuid4()))))

    await deal_case.add(make_deal(later(1), code="20261016-A002"))

    assert await deal_case.deals.exists(make_deal(code="20261016-A002").id) is True
