"""BANT Label 참조 위반의 오류 문구 계약: 내부 repr을 응답으로 내보내지 않는다.

Fake와 SQL(PostgreSQL)에 같은 기대값. 없는 Label이거나 다른 구분의 Label을 가리키면
InvalidReferenceError이고, 문구는 어떤 항목이 문제인지만 말한다(`BantSelection(...)`·`UUID(...)`
같은 객체 표현이 들어가면 안 된다). 오류 뒤에도 같은 트랜잭션을 계속 쓸 수 있다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.common.errors import InvalidReferenceError
from tests.factories import later, make_bant, make_deal
from tests.support.ids import new_id

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
    """없는 Label로 Deal을 저장하면 객체 표현 없는 InvalidReferenceError가 나는지 확인한다."""
    # given: 존재하지 않는 BANT Label을 고른 Deal이 있다
    deal = make_deal(code=CODE, bant=make_bant(budget=BantLabelId(new_id())))

    # when: Deal을 저장한다
    with pytest.raises(InvalidReferenceError) as raised:
        await deal_case.add(deal)

    # then: InvalidReferenceError이고 문구에 내부 객체 표현이 없다
    _assert_clean(raised.value)
    # when: Deal이 저장되었는지 조회한다
    exists = await deal_case.deals.exists(deal.id)

    # then: 저장되지 않았다
    assert exists is False


async def test_adding_with_a_label_of_another_category_is_an_invalid_reference(
    deal_case: DealCase,
) -> None:
    """다른 구분의 Label로 Deal을 저장하면 InvalidReferenceError인지 확인한다."""
    # given: 필요 구분 Label과 이를 예산에 고른 Deal이 있다
    need = await deal_case.new_label(BantCategory.NEED, "필요 가")
    deal = make_deal(code=CODE, bant=make_bant(budget=need.id))  # 필요 Label을 예산에 선택

    # when: Deal을 저장한다
    with pytest.raises(InvalidReferenceError) as raised:
        await deal_case.add(deal)

    # then: InvalidReferenceError이고 문구에 내부 객체 표현이 없다
    _assert_clean(raised.value)


async def test_updating_to_an_unknown_label_is_an_invalid_reference_and_keeps_the_old_one(
    deal_case: DealCase,
) -> None:
    """없는 Label로 수정하면 InvalidReferenceError이고 기존 Label이 유지되는지 확인한다."""
    # given: 예산 Label을 고른 Deal이 저장되어 있다
    budget = await deal_case.new_label(BantCategory.BUDGET, "예산 가")
    deal = make_deal(later(1), code=CODE, bant=make_bant(budget=budget.id))
    await deal_case.add(deal)

    # when: 없는 Label로 Deal을 수정한다
    with pytest.raises(InvalidReferenceError) as raised:
        await deal_case.revise(deal.id, bant=make_bant(budget=BantLabelId(new_id())))

    # then: InvalidReferenceError이고 문구에 내부 객체 표현이 없다
    _assert_clean(raised.value)
    # when: Deal을 다시 읽는다
    stored = await deal_case.deals.get(deal.id)

    # then: 기존 Label 선택이 그대로다
    assert stored.bant == make_bant(budget=budget.id)


async def test_the_transaction_stays_usable_after_the_invalid_reference(
    deal_case: DealCase,
) -> None:
    """참조 오류 뒤에도 같은 트랜잭션을 계속 쓸 수 있는지 확인한다."""
    # given: 없는 Label을 고른 Deal 저장이 InvalidReferenceError로 실패했다
    with pytest.raises(InvalidReferenceError):
        await deal_case.add(make_deal(code=CODE, bant=make_bant(need=BantLabelId(new_id()))))

    # when: 올바른 Deal을 이어서 저장한다
    await deal_case.add(make_deal(later(1), code="20261016-A002"))

    # when: 저장 여부를 조회한다
    exists = await deal_case.deals.exists(make_deal(code="20261016-A002").id)

    # then: 올바른 Deal이 저장되어 있다
    assert exists is True
