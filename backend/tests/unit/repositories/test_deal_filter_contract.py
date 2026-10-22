"""DealRepository.search/count의 확장 필터 계약(R3, AC-22a~22c): Fake와 SQL에 같은 기대값.

forecast 정확 일치(vendor_id·solution은 test_deal_search_contract), 연/분기(Expected Close
기준, 양끝 포함). 모든 조건은 count와 같은 결과를 내고 페이지와 무관하게 센다.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery
from tests.factories import later, make_deal

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase


async def _codes(case: DealCase, **criteria: object) -> list[str]:
    found = await case.deals.search(DealQuery(**criteria))  # type: ignore[arg-type]
    return sorted(item.deal.id.value for item in found)


async def _count(case: DealCase, **criteria: object) -> int:
    return int(await case.deals.count(DealQuery(**criteria)))  # type: ignore[arg-type]


def _code(number: int) -> str:
    return f"20261016-A{number:03d}"


class TestForecast:
    async def test_forecast_matches_the_forecast_key(self, deal_case: DealCase) -> None:
        await deal_case.add(make_deal(later(1), code=_code(1), forecast_key="pipeline"))
        await deal_case.add(make_deal(later(2), code=_code(2), forecast_key="commit"))
        await deal_case.add(make_deal(later(3), code=_code(3), forecast_key="lost"))

        assert await _codes(deal_case, forecast_key="commit") == [_code(2)]
        assert await _codes(deal_case, forecast_key="lost") == [_code(3)]

    async def test_an_unknown_forecast_key_is_zero_results_not_an_error(
        self, deal_case: DealCase
    ) -> None:
        await deal_case.add(make_deal(later(1), code=_code(1)))

        assert await _codes(deal_case, forecast_key="no_such_forecast") == []
        assert await _count(deal_case, forecast_key="no_such_forecast") == 0


class TestYearAndQuarter:
    async def _by_day(self, case: DealCase, days: list[date]) -> dict[date, str]:
        codes: dict[date, str] = {}
        for number, day in enumerate(days, start=1):
            await case.add(make_deal(later(number), code=_code(number), revenue_date=day))
            codes[day] = _code(number)
        return codes

    async def test_a_year_alone_includes_january_first_and_december_31(
        self, deal_case: DealCase
    ) -> None:
        days = [date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1)]
        codes = await self._by_day(deal_case, days)

        found = await _codes(deal_case, year=2026)

        assert found == sorted([codes[date(2026, 1, 1)], codes[date(2026, 12, 31)]])
        assert await _count(deal_case, year=2026) == 2

    @pytest.mark.parametrize(
        ("quarter", "first_day", "last_day"),
        [
            (1, date(2026, 1, 1), date(2026, 3, 31)),
            (2, date(2026, 4, 1), date(2026, 6, 30)),
            (3, date(2026, 7, 1), date(2026, 9, 30)),
            (4, date(2026, 10, 1), date(2026, 12, 31)),
        ],
    )
    async def test_a_quarter_includes_its_first_and_last_day_and_nothing_around_them(
        self, deal_case: DealCase, quarter: int, first_day: date, last_day: date
    ) -> None:
        before = date.fromordinal(first_day.toordinal() - 1)
        after = date.fromordinal(last_day.toordinal() + 1)
        codes = await self._by_day(deal_case, [before, first_day, last_day, after])

        found = await _codes(deal_case, year=2026, quarter=quarter)

        assert found == sorted([codes[first_day], codes[last_day]])
        assert await _count(deal_case, year=2026, quarter=quarter) == 2

    async def test_the_same_quarter_of_another_year_is_not_included(
        self, deal_case: DealCase
    ) -> None:
        codes = await self._by_day(deal_case, [date(2026, 5, 1), date(2027, 5, 1)])

        assert await _codes(deal_case, year=2027, quarter=2) == [codes[date(2027, 5, 1)]]

    async def test_the_quarter_is_combined_with_the_updated_period_using_and(
        self, deal_case: DealCase
    ) -> None:
        # (Expected Close, 등록 시각): 분기·기간 모두 맞아야 한다
        rows = [
            (date(2026, 5, 20), datetime(2026, 6, 10, 12).astimezone()),  # 둘 다 맞음
            (date(2026, 5, 21), datetime(2026, 7, 10, 12).astimezone()),  # 기간 밖
            (date(2026, 8, 1), datetime(2026, 6, 10, 12).astimezone()),  # 분기 밖
        ]
        for number, (day, created) in enumerate(rows, start=1):
            await deal_case.add(make_deal(created, code=_code(number), revenue_date=day))

        found = await _codes(
            deal_case,
            year=2026,
            quarter=2,
            updated_from=date(2026, 6, 1),
            updated_to=date(2026, 6, 30),
        )

        assert found == [_code(1)]

    async def test_the_year_filter_combines_with_the_page_and_total(
        self, deal_case: DealCase
    ) -> None:
        await self._by_day(deal_case, [date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5)])
        await self._by_day_other_year(deal_case)

        page = await deal_case.deals.search(DealQuery(year=2026, offset=1, limit=1))

        assert len(page) == 1
        assert await deal_case.deals.count(DealQuery(year=2026, offset=1, limit=1)) == 3

    async def _by_day_other_year(self, case: DealCase) -> None:
        await case.add(make_deal(later(9), code=_code(9), revenue_date=date(2027, 2, 5)))
