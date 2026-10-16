"""코드·BANT Label 삭제의 사용 중 계약(R3, AC-14·15): Deal이 쓰는 항목은 지워지지 않는다.

Fake와 SQL(PostgreSQL)에 같은 기대값. `CodeRepository.delete`·`BantLabelRepository.delete`는
Deal이 연결한 항목이면 행을 남기고 CodeInUseError·LabelInUseError(실제 연결 수 포함)를 낸다.
SQL은 FK(RESTRICT) 위반을 이 오류로 바꾸며, 오류 뒤에도 같은 트랜잭션을 계속 쓸 수 있어야 한다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.bant.errors import LabelInUseError
from app.domain.bant.values import BantCategory
from app.domain.code.errors import CodeInUseError
from app.domain.code.values import CodeKind
from tests.factories import later, make_bant, make_deal

if TYPE_CHECKING:
    from app.domain.code.entities import Code
    from tests.unit.repositories.deal_case import DealCase


async def _code(case: DealCase, kind: CodeKind, key: str) -> Code:
    found: Code = next(c for c in await case.codes.list(kind) if c.key.value == key)
    return found


class TestCodes:
    @pytest.mark.parametrize(
        ("kind", "key", "deal_fields"),
        [
            (CodeKind.STATUS, "introduction", {"status_key": "introduction"}),
            (CodeKind.FORECAST, "best", {"forecast_key": "best"}),
        ],
    )
    async def test_a_code_used_by_deals_is_not_deleted_and_reports_the_count(
        self, deal_case: DealCase, kind: CodeKind, key: str, deal_fields: dict[str, Any]
    ) -> None:
        code = await _code(deal_case, kind, key)
        await deal_case.add(make_deal(later(1), code="20261016-A001", **deal_fields))
        await deal_case.add(make_deal(later(2), code="20261016-A002", **deal_fields))

        with pytest.raises(CodeInUseError) as raised:
            await deal_case.codes.delete(code.id)

        assert str(raised.value) == "사용 중인 코드는 삭제할 수 없습니다. (Deal 2건)"
        assert (await deal_case.codes.get(code.id)).key.value == key

    async def test_the_transaction_stays_usable_after_the_refusal(
        self, deal_case: DealCase
    ) -> None:
        code = await _code(deal_case, CodeKind.FORECAST, "best")
        await deal_case.add(make_deal(later(1), code="20261016-A001", forecast_key="best"))

        with pytest.raises(CodeInUseError):
            await deal_case.codes.delete(code.id)

        await deal_case.add(make_deal(later(2), code="20261016-A002"))
        assert await deal_case.deals.count(DealQuery()) == 2

    async def test_an_unused_code_is_deleted(self, deal_case: DealCase) -> None:
        code = await _code(deal_case, CodeKind.FORECAST, "best")
        await deal_case.add(make_deal(later(1), code="20261016-A001", forecast_key="commit"))

        await deal_case.codes.delete(code.id)

        keys = [c.key.value for c in await deal_case.codes.list(CodeKind.FORECAST)]
        assert "best" not in keys

    async def test_the_code_becomes_deletable_once_the_last_deal_is_gone(
        self, deal_case: DealCase
    ) -> None:
        code = await _code(deal_case, CodeKind.FORECAST, "best")
        deal = make_deal(later(1), code="20261016-A001", forecast_key="best")
        await deal_case.add(deal)
        await deal_case.deals.delete(deal.id)

        await deal_case.codes.delete(code.id)

        keys = [c.key.value for c in await deal_case.codes.list(CodeKind.FORECAST)]
        assert "best" not in keys


class TestLabels:
    async def test_a_label_selected_by_deals_is_not_deleted_and_reports_the_count(
        self, deal_case: DealCase
    ) -> None:
        label = await deal_case.new_label(BantCategory.BUDGET, "예산 가")
        for number in (1, 2, 3):
            await deal_case.add(
                make_deal(
                    later(number),
                    code=f"20261016-A00{number}",
                    bant=make_bant(budget=label.id),
                )
            )

        with pytest.raises(LabelInUseError) as raised:
            await deal_case.labels.delete(label.id)

        assert str(raised.value) == "사용 중인 Label은 삭제할 수 없습니다. (Deal 3건)"
        assert (await deal_case.labels.get(label.id)).name == "예산 가"

    async def test_an_unused_label_is_deleted_even_if_another_label_of_the_category_is_used(
        self, deal_case: DealCase
    ) -> None:
        used = await deal_case.new_label(BantCategory.BUDGET, "예산 가")
        idle = await deal_case.new_label(BantCategory.BUDGET, "예산 나")
        await deal_case.add(
            make_deal(later(1), code="20261016-A001", bant=make_bant(budget=used.id))
        )

        await deal_case.labels.delete(idle.id)

        names = [x.name for x in await deal_case.labels.list(BantCategory.BUDGET)]
        assert "예산 나" not in names
        assert "예산 가" in names

    async def test_the_label_becomes_deletable_once_no_deal_selects_it(
        self, deal_case: DealCase
    ) -> None:
        label = await deal_case.new_label(BantCategory.NEED, "필요 가")
        deal = make_deal(later(1), code="20261016-A001", bant=make_bant(need=label.id))
        await deal_case.add(deal)
        await deal_case.revise(deal.id, bant=make_bant())

        await deal_case.labels.delete(label.id)

        names = [x.name for x in await deal_case.labels.list(BantCategory.NEED)]
        assert "필요 가" not in names
