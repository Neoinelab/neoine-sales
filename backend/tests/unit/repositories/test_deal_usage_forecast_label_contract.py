"""DealRepository 사용 수 집계 계약: Forecast와 BANT Label.

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
        """Deal이 없으면 Forecast별 사용 수가 비어 있다."""
        # when: Forecast별 사용 수를 센다
        counts = await deal_case.deals.count_by_forecast()

        # then: 0이 아닌 항목이 없다
        assert _nonzero(counts) == {}

    async def test_deals_are_grouped_by_forecast_key(self, deal_case: DealCase) -> None:
        """Deal은 Forecast 키별로 묶어 센다."""
        # given: Forecast가 섞인 Deal 5건
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

        # when: Forecast별 사용 수를 센다
        counts = await deal_case.deals.count_by_forecast()

        # then: 키별 건수다
        assert _nonzero(counts) == {"pipeline": 2, "commit": 1, "lost": 1, "won": 1}

    async def test_the_counts_do_not_mix_up_status_and_forecast_keys(
        self, deal_case: DealCase
    ) -> None:
        """Status 키와 Forecast 키 집계는 서로 섞이지 않는다."""
        # given: Status와 Forecast 키가 다른 Deal 1건
        await deal_case.add(
            make_deal(code="20261016-A001", status_key="introduction", forecast_key="best")
        )

        # when: Forecast별과 Status별 사용 수를 각각 센다
        by_forecast = await deal_case.deals.count_by_forecast()
        by_status = await deal_case.deals.count_by_status()

        # then: 각자 자기 키로만 센다
        assert _nonzero(by_forecast) == {"best": 1}
        assert _nonzero(by_status) == {"introduction": 1}

    async def test_counts_follow_changes_and_deletions(self, deal_case: DealCase) -> None:
        """사용 수는 Forecast 변경과 Deal 삭제를 따라간다."""
        # given: Deal 2건
        moved = make_deal(later(1), code="20261016-A001")
        removed = make_deal(later(2), code="20261016-A002", forecast_key="commit")
        await deal_case.add(moved)
        await deal_case.add(removed)

        # when: 한 건의 Forecast를 바꾸고 다른 한 건을 삭제한 뒤 센다
        await deal_case.revise(moved.id, sync=make_deal(forecast_key="best").sync)
        await deal_case.deals.delete(removed.id)
        counts = await deal_case.deals.count_by_forecast()

        # then: 바뀐 키 1건만 남는다
        assert _nonzero(counts) == {"best": 1}


class TestCountByBantLabel:
    async def test_an_empty_repository_has_no_counts(self, deal_case: DealCase) -> None:
        """Deal이 없으면 Label별 사용 수가 비어 있다."""
        # when: Label별 사용 수를 센다
        counts = await deal_case.deals.count_by_bant_label()

        # then: 0이 아닌 항목이 없다
        assert _nonzero(counts) == {}

    async def test_each_selected_label_counts_the_deals_that_chose_it(
        self, deal_case: DealCase
    ) -> None:
        """선택된 Label마다 그것을 고른 Deal 수를 센다."""
        # given: Label 3개와 서로 다르게 선택한 Deal 4건
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

        # when: Label별 사용 수를 센다
        counts = await deal_case.deals.count_by_bant_label()

        # then: Label마다 고른 Deal 수다
        assert _nonzero(counts) == {budget.id: 2, other_budget.id: 1, need.id: 1}

    async def test_counts_follow_label_changes_and_deletions(self, deal_case: DealCase) -> None:
        """사용 수는 Label 변경과 Deal 삭제를 따라간다."""
        # given: 같은 Label을 고른 Deal 2건과 다른 Label 하나
        first = await deal_case.new_label(BantCategory.BUDGET, "예산 가")
        second = await deal_case.new_label(BantCategory.BUDGET, "예산 나")
        kept = make_deal(later(1), code="20261016-A001", bant=make_bant(budget=first.id))
        removed = make_deal(later(2), code="20261016-A002", bant=make_bant(budget=first.id))
        await deal_case.add(kept)
        await deal_case.add(removed)

        # when: 한 건의 Label을 바꾸고 다른 한 건을 삭제한 뒤 센다
        await deal_case.revise(kept.id, bant=make_bant(budget=second.id))
        await deal_case.deals.delete(removed.id)
        counts = await deal_case.deals.count_by_bant_label()

        # then: 바뀐 Label 1건만 남는다
        assert _nonzero(counts) == {second.id: 1}
