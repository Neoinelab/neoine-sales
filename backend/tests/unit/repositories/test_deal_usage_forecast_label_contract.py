"""DealRepository 사용 수 집계 계약(R3, AC-14·15): Forecast와 BANT Label.

Fake와 SQL(PostgreSQL)에 같은 기대값. 0건인 항목은 빠져도 된다(0은 무시하고 비교한다).
Label 사용 수는 Deal이 그 Label을 선택한 구분 한 곳이면 1건이다.
"""

from typing import TYPE_CHECKING

from app.domain.bant.values import BantCategory
from tests.factories import later, make_bant, make_deal

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tests.unit.repositories.deal_case import DealCase


def _nonzero(counts: Mapping[object, int]) -> dict[object, int]:
    return {key: count for key, count in counts.items() if count}


class TestCountByForecast:
    async def test_an_empty_repository_has_no_counts(self, deal_case: DealCase) -> None:
        assert _nonzero(await deal_case.deals.count_by_forecast()) == {}

    async def test_deals_are_grouped_by_forecast_key(self, deal_case: DealCase) -> None:
        rows = [
            ("pipeline", "prospecting"),
            ("pipeline", "introduction"),
            ("commit", "prospecting"),
            ("lost", "prospecting"),
            ("won", "contract_completed"),
        ]
        for n, (forecast, status) in enumerate(rows, start=1):
            await deal_case.add(
                make_deal(
                    later(n), code=f"20261016-A00{n}", forecast_key=forecast, status_key=status
                )
            )

        counts = await deal_case.deals.count_by_forecast()

        assert _nonzero(counts) == {"pipeline": 2, "commit": 1, "lost": 1, "won": 1}

    async def test_the_counts_do_not_mix_up_status_and_forecast_keys(
        self, deal_case: DealCase
    ) -> None:
        await deal_case.add(
            make_deal(code="20261016-A001", status_key="introduction", forecast_key="best")
        )

        assert _nonzero(await deal_case.deals.count_by_forecast()) == {"best": 1}
        assert _nonzero(await deal_case.deals.count_by_status()) == {"introduction": 1}

    async def test_counts_follow_changes_and_deletions(self, deal_case: DealCase) -> None:
        moved = make_deal(later(1), code="20261016-A001")
        removed = make_deal(later(2), code="20261016-A002", forecast_key="commit")
        await deal_case.add(moved)
        await deal_case.add(removed)

        await deal_case.revise(moved.id, sync=make_deal(forecast_key="best").sync)
        await deal_case.deals.delete(removed.id)

        assert _nonzero(await deal_case.deals.count_by_forecast()) == {"best": 1}


class TestCountByBantLabel:
    async def test_an_empty_repository_has_no_counts(self, deal_case: DealCase) -> None:
        assert _nonzero(await deal_case.deals.count_by_bant_label()) == {}

    async def test_each_selected_label_counts_the_deals_that_chose_it(
        self, deal_case: DealCase
    ) -> None:
        budget = await deal_case.new_label(BantCategory.BUDGET, "예산 가")
        other_budget = await deal_case.new_label(BantCategory.BUDGET, "예산 나")
        need = await deal_case.new_label(BantCategory.NEED, "필요 가")
        await deal_case.add(
            make_deal(
                later(1),
                code="20261016-A001",
                bant=make_bant(budget=budget.id, need=need.id),
            )
        )
        await deal_case.add(
            make_deal(later(2), code="20261016-A002", bant=make_bant(budget=budget.id))
        )
        await deal_case.add(
            make_deal(later(3), code="20261016-A003", bant=make_bant(budget=other_budget.id))
        )
        await deal_case.add(make_deal(later(4), code="20261016-A004"))

        counts = await deal_case.deals.count_by_bant_label()

        assert _nonzero(counts) == {budget.id: 2, other_budget.id: 1, need.id: 1}

    async def test_counts_follow_label_changes_and_deletions(self, deal_case: DealCase) -> None:
        first = await deal_case.new_label(BantCategory.BUDGET, "예산 가")
        second = await deal_case.new_label(BantCategory.BUDGET, "예산 나")
        kept = make_deal(later(1), code="20261016-A001", bant=make_bant(budget=first.id))
        removed = make_deal(later(2), code="20261016-A002", bant=make_bant(budget=first.id))
        await deal_case.add(kept)
        await deal_case.add(removed)

        await deal_case.revise(kept.id, bant=make_bant(budget=second.id))
        await deal_case.deals.delete(removed.id)

        assert _nonzero(await deal_case.deals.count_by_bant_label()) == {second.id: 1}
