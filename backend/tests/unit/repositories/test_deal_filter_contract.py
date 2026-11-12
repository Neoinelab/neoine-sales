"""DealRepository.search/count의 확장 필터 계약: Fake와 SQL에 같은 기대값.

forecast_keys 중 하나와 일치(OR; vendor_id·solution은 test_deal_search_contract), 연/분기
(Expected Close 기준, 양끝 포함). 모든 조건은 count와 같은 결과를 내고 페이지와 무관하게 센다.
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
        """forecast_keys 하나로 해당 Forecast의 Deal만 찾는다."""
        # given: pipeline·commit·lost Deal 셋
        await deal_case.add(make_deal(later(1), code=_code(1), forecast_key="pipeline"))
        await deal_case.add(make_deal(later(2), code=_code(2), forecast_key="commit"))
        await deal_case.add(make_deal(later(3), code=_code(3), forecast_key="lost"))

        # when: commit과 lost를 각각 조건으로 검색한다 (전제: Fake·SQL 공통)
        commit_codes = await _codes(deal_case, forecast_keys=frozenset({"commit"}))
        lost_codes = await _codes(deal_case, forecast_keys=frozenset({"lost"}))

        # then: 각 Forecast의 Deal만 나온다
        assert commit_codes == [_code(2)]
        assert lost_codes == [_code(3)]

    async def test_forecast_keys_match_any_of_the_keys(self, deal_case: DealCase) -> None:
        """forecast_keys 여러 개는 하나라도 일치하면 찾는다."""
        # given: pipeline·commit·lost Deal 셋
        await deal_case.add(make_deal(later(1), code=_code(1), forecast_key="pipeline"))
        await deal_case.add(make_deal(later(2), code=_code(2), forecast_key="commit"))
        await deal_case.add(make_deal(later(3), code=_code(3), forecast_key="lost"))

        # when: pipeline·commit을 함께, lost를 따로 검색·집계한다 (전제: Fake·SQL 공통)
        both = frozenset({"pipeline", "commit"})
        both_codes = await _codes(deal_case, forecast_keys=both)
        both_count = await _count(deal_case, forecast_keys=both)
        lost_codes = await _codes(deal_case, forecast_keys=frozenset({"lost"}))

        # then: 두 Forecast의 Deal만 나오고 건수가 같다
        assert both_codes == [_code(1), _code(2)]
        assert both_count == 2
        assert lost_codes == [_code(3)]

    async def test_without_forecast_keys_every_forecast_is_returned(
        self, deal_case: DealCase
    ) -> None:
        """forecast_keys가 없으면 모든 Forecast를 돌려준다."""
        # given: pipeline·lost Deal 둘
        await deal_case.add(make_deal(later(1), code=_code(1), forecast_key="pipeline"))
        await deal_case.add(make_deal(later(2), code=_code(2), forecast_key="lost"))

        # when: Forecast 조건 없이 검색한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case)

        # then: 둘 다 나온다
        assert found == [_code(1), _code(2)]

    async def test_unknown_keys_next_to_known_ones_match_only_the_known(
        self, deal_case: DealCase
    ) -> None:
        """모르는 키가 섞여도 아는 키에 맞는 Deal만 찾는다."""
        # given: pipeline·commit Deal 둘
        await deal_case.add(make_deal(later(1), code=_code(1), forecast_key="pipeline"))
        await deal_case.add(make_deal(later(2), code=_code(2), forecast_key="commit"))

        # when: 아는 키와 모르는 키·빈 키를 함께 조건으로 검색·집계한다 (전제: Fake·SQL 공통)
        keys = frozenset({"commit", "no_such", ""})
        found = await _codes(deal_case, forecast_keys=keys)
        count = await _count(deal_case, forecast_keys=keys)

        # then: 아는 키의 Deal만 나오고 건수가 같다
        assert found == [_code(2)]
        assert count == 1

    async def test_unknown_keys_only_match_nothing(self, deal_case: DealCase) -> None:
        """모르는 키만 있으면 아무것도 찾지 않는다."""
        # given: Deal 하나
        await deal_case.add(make_deal(later(1), code=_code(1)))

        # when: 모르는 키만 조건으로 검색·집계한다 (전제: Fake·SQL 공통)
        only_unknown = frozenset({"no_such"})
        found = await _codes(deal_case, forecast_keys=only_unknown)
        count = await _count(deal_case, forecast_keys=only_unknown)

        # then: 결과와 건수가 0이다
        assert found == []
        assert count == 0

    async def test_an_unknown_forecast_key_is_zero_results_not_an_error(
        self, deal_case: DealCase
    ) -> None:
        """없는 Forecast 키는 오류가 아니라 결과 0건이다."""
        # given: Deal 하나
        await deal_case.add(make_deal(later(1), code=_code(1)))

        # when: 없는 Forecast 키로 검색·집계한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, forecast_keys=frozenset({"no_such_forecast"}))
        count = await _count(deal_case, forecast_keys=frozenset({"no_such_forecast"}))

        # then: 오류 없이 0건이다
        assert found == []
        assert count == 0


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
        """연도만 지정하면 1월 1일과 12월 31일을 포함한다."""
        # given: 전년 말, 해당 연도 처음·끝, 다음 해 처음에 끝나는 Deal 넷
        days = [date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1)]
        codes = await self._by_day(deal_case, days)

        # when: 2026년으로 검색·집계한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, year=2026)
        count = await _count(deal_case, year=2026)

        # then: 2026년 처음·끝 Deal만 나오고 건수는 2다
        assert found == sorted([codes[date(2026, 1, 1)], codes[date(2026, 12, 31)]])
        assert count == 2

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
        """분기는 첫날과 마지막 날을 포함하고 그 앞뒤는 제외한다."""
        # given: 분기 첫날 전날, 첫날, 마지막 날, 다음 날이 예상 마감일인 Deal 넷
        before = date.fromordinal(first_day.toordinal() - 1)
        after = date.fromordinal(last_day.toordinal() + 1)
        codes = await self._by_day(deal_case, [before, first_day, last_day, after])

        # when: 해당 분기로 검색·집계한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, year=2026, quarters=frozenset({quarter}))
        count = await _count(deal_case, year=2026, quarters=frozenset({quarter}))

        # then: 첫날·마지막 날 Deal만 나오고 건수는 2다
        assert found == sorted([codes[first_day], codes[last_day]])
        assert count == 2

    async def test_the_same_quarter_of_another_year_is_not_included(
        self, deal_case: DealCase
    ) -> None:
        """다른 해의 같은 분기는 포함하지 않는다."""
        # given: 2026년 5월과 2027년 5월 Deal
        codes = await self._by_day(deal_case, [date(2026, 5, 1), date(2027, 5, 1)])

        # when: 2027년 2분기로 검색한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, year=2027, quarters=frozenset({2}))

        # then: 2027년 Deal만 나온다
        assert found == [codes[date(2027, 5, 1)]]

    async def test_the_quarter_is_combined_with_the_updated_period_using_and(
        self, deal_case: DealCase
    ) -> None:
        """분기와 최종 업데이트 기간은 AND로 결합한다."""
        # (Expected Close, 등록 시각): 분기·기간 모두 맞아야 한다
        # given: 분기·기간이 모두 맞는 Deal, 기간 밖 Deal, 분기 밖 Deal
        rows = [
            (date(2026, 5, 20), datetime(2026, 6, 10, 12).astimezone()),  # 둘 다 맞음
            (date(2026, 5, 21), datetime(2026, 7, 10, 12).astimezone()),  # 기간 밖
            (date(2026, 8, 1), datetime(2026, 6, 10, 12).astimezone()),  # 분기 밖
        ]
        for number, (day, created) in enumerate(rows, start=1):
            await deal_case.add(make_deal(created, code=_code(number), revenue_date=day))

        # when: 2분기와 6월 기간으로 검색한다 (전제: Fake·SQL 공통)
        found = await _codes(
            deal_case,
            year=2026,
            quarters=frozenset({2}),
            updated_from=date(2026, 6, 1),
            updated_to=date(2026, 6, 30),
        )

        # then: 둘 다 맞는 Deal만 나온다
        assert found == [_code(1)]

    async def test_separated_quarters_include_only_their_boundary_days(
        self, deal_case: DealCase
    ) -> None:
        """떨어진 분기들은 각 분기 경계일만 포함한다."""
        # given: 1~3분기 경계일과 전년 날짜가 예상 마감일인 Deal들
        days = [
            date(2026, 1, 1),
            date(2026, 3, 31),
            date(2026, 4, 1),
            date(2026, 6, 30),
            date(2026, 7, 1),
            date(2026, 9, 30),
            date(2026, 10, 1),
            date(2025, 8, 1),
        ]
        codes = await self._by_day(deal_case, days)
        wanted = sorted(codes[d] for d in days[:2] + days[4:6])

        # when: 1분기·3분기로 검색·집계한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, year=2026, quarters=frozenset({1, 3}))
        count = await _count(deal_case, year=2026, quarters=frozenset({1, 3}))

        # then: 두 분기의 경계일 Deal만 나오고 건수는 4다
        assert found == wanted
        assert count == 4

    async def test_the_quarter_between_separated_quarters_is_not_included(
        self, deal_case: DealCase
    ) -> None:
        """떨어진 분기 사이의 분기는 포함하지 않는다."""
        # given: 2분기와 1분기에 속한 Deal
        codes = await self._by_day(deal_case, [date(2026, 5, 15), date(2026, 2, 15)])

        # when: 1분기·3분기로 검색한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, year=2026, quarters=frozenset({1, 3}))

        # then: 1분기 Deal만 나온다
        assert found == [codes[date(2026, 2, 15)]]

    async def test_adjacent_quarters_include_both_and_exclude_the_others(
        self, deal_case: DealCase
    ) -> None:
        """이웃한 분기는 둘 다 포함하고 나머지는 제외한다."""
        # given: 1~3분기 경계일이 예상 마감일인 Deal 넷
        days = [date(2026, 3, 31), date(2026, 4, 1), date(2026, 6, 30), date(2026, 7, 1)]
        codes = await self._by_day(deal_case, days)

        # when: 1분기·2분기로 검색한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, year=2026, quarters=frozenset({1, 2}))

        # then: 앞 세 Deal만 나온다
        assert found == sorted(codes[d] for d in days[:3])

    async def test_all_four_quarters_equal_the_whole_year(self, deal_case: DealCase) -> None:
        """네 분기를 모두 고르면 그 해 전체와 같다."""
        # given: 전년 말, 해당 연도 처음·끝, 다음 해 처음 Deal 넷
        days = [date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1)]
        codes = await self._by_day(deal_case, days)

        # when: 1~4분기 전부로 검색한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, year=2026, quarters=frozenset({1, 2, 3, 4}))

        # then: 해당 연도 Deal만 나온다
        assert found == sorted([codes[days[1]], codes[days[2]]])

    async def test_quarters_of_another_year_are_not_included(self, deal_case: DealCase) -> None:
        """다른 해의 분기는 포함하지 않는다."""
        # given: 2026년 2월과 2027년 2월 Deal
        codes = await self._by_day(deal_case, [date(2026, 2, 1), date(2027, 2, 1)])

        # when: 2027년 1분기·3분기로 검색한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, year=2027, quarters=frozenset({1, 3}))

        # then: 2027년 Deal만 나온다
        assert found == [codes[date(2027, 2, 1)]]

    async def test_chosen_quarters_without_a_year_use_the_filled_year(
        self, deal_case: DealCase
    ) -> None:
        """연도 없이 고른 분기는 채운 연도로 검색한다."""
        # given: 올해 1·2분기와 전년 1분기 Deal
        codes = await self._by_day(
            deal_case, [date(2026, 2, 1), date(2026, 5, 1), date(2025, 2, 1)]
        )
        # when: 연도를 채운 뒤(기준일 2026-10-19) 1분기·3분기로 검색한다 (전제: Fake·SQL 공통)
        query = DealQuery(quarters=frozenset({1, 3})).with_year_for(date(2026, 10, 19))

        found = await deal_case.deals.search(query)

        # then: 올해 1분기 Deal만 나온다
        assert sorted(item.deal.id.value for item in found) == [codes[date(2026, 2, 1)]]

    async def test_the_year_filter_combines_with_the_page_and_total(
        self, deal_case: DealCase
    ) -> None:
        """연도 조건은 페이지·전체 건수와 함께 동작한다."""
        # given: 2026년 Deal 3건과 2027년 Deal 1건
        await self._by_day(deal_case, [date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5)])
        await self._by_day_other_year(deal_case)

        # when: 2026년의 두 번째 한 건을 검색하고 건수를 센다 (전제: Fake·SQL 공통)
        page = await deal_case.deals.search(DealQuery(year=2026, offset=1, limit=1))

        total = await deal_case.deals.count(DealQuery(year=2026, offset=1, limit=1))

        # then: 한 건이 나오고 전체 건수는 3이다
        assert len(page) == 1
        assert total == 3

    async def _by_day_other_year(self, case: DealCase) -> None:
        await case.add(make_deal(later(9), code=_code(9), revenue_date=date(2027, 2, 5)))
