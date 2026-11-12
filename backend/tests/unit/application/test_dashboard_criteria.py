"""DashboardCriteria: Dashboard 각 숫자의 조건을 정의하는 단일 출처.

프런트 Drill-down URL은 이 메서드들과 1:1이므로, 각 메서드가 만드는 `DealQuery`의 조건을
모두 고정한다.
"""

from datetime import date

import pytest

from app.application.dashboard.criteria import DashboardCriteria
from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
from app.application.ports.deal_repository import DealQuery
from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.deal.risk import RiskBasis
from app.domain.forecast.period import ForecastPeriod
from app.domain.vendor.values import VendorId
from tests.support.ids import new_id
from tests.support.user_ids import uid

OWNER = uid("dash-owner")
VENDOR = VendorId(new_id())
BASIS = RiskBasis(today=date(2026, 10, 23), stale_days=14)
TODAY = date(2026, 10, 23)


def _full() -> DashboardCriteria:
    return DashboardCriteria(
        period=ForecastPeriod(year=2025, quarters=frozenset({2})),
        owner_user_id=OWNER,
        vendor_id=VENDOR,
    )


def test_forecast_criteria_carries_period_owner_and_vendor() -> None:
    """Forecast 요약 조건은 기간·담당자·Vendor를 그대로 담는다.

    테스트 코드: DSH-008
    """
    # given: 2025년 Q2, 담당자, Vendor 조건
    criteria = _full()

    # when: Forecast 요약 조건으로 바꾼다
    forecast = criteria.forecast_criteria()

    # then: 기간·담당자·Vendor가 그대로다
    assert forecast == ForecastCriteria(
        period=ForecastPeriod(year=2025, quarters=frozenset({2})),
        owner_user_id=OWNER,
        vendor_id=VENDOR,
    )


def test_status_query_excludes_lost_and_keeps_period_owner_vendor() -> None:
    """Status 조건은 Lost를 빼고 기간·담당자·Vendor를 따른다.

    테스트 코드: DSH-011
    """
    # given: 2025년 Q2, 담당자, Vendor 조건
    criteria = _full()

    # when: Status 숫자의 Deal 목록 조건을 만든다
    query = criteria.status_query()

    # then: 기간·담당자·Vendor가 같고 Lost 제외이며 다른 조건은 없다
    assert (query.year, query.quarters, query.month) == (2025, frozenset({2}), None)
    assert query.owner_user_id == OWNER
    assert query.vendor_id == VENDOR
    assert query.forecast_outcome is ForecastOutcomeFilter.NOT_LOST
    assert (query.status_key, query.forecast_keys) == (None, None)
    assert (query.overdue, query.stale) == (False, False)


def test_open_query_selects_open_outcome() -> None:
    """Open 조건은 기간·담당자·Vendor와 Open outcome이다.

    테스트 코드: DSH-023
    """
    # given: 2025년 Q2, 담당자, Vendor 조건
    criteria = _full()

    # when: Open 합계의 Deal 목록 조건을 만든다
    query = criteria.open_query()

    # then: 같은 기간·담당자·Vendor와 Open outcome이다
    assert (query.year, query.quarters) == (2025, frozenset({2}))
    assert (query.owner_user_id, query.vendor_id) == (OWNER, VENDOR)
    assert query.forecast_outcome is ForecastOutcomeFilter.OPEN


def test_year_query_drops_quarter() -> None:
    """분기 행 조건은 고른 분기를 버리고 연도·담당자·Vendor만 남긴다.

    테스트 코드: DSH-014
    """
    # given: 2025년 Q2, 담당자, Vendor 조건
    criteria = _full()

    # when: 분기 행의 Deal 목록 조건을 만든다
    query = criteria.year_query()

    # then: 분기·월·outcome 없이 연도·담당자·Vendor다
    assert (query.year, query.quarters, query.month) == (2025, None, None)
    assert (query.owner_user_id, query.vendor_id) == (OWNER, VENDOR)
    assert query.forecast_outcome is None


def test_queries_without_owner_and_vendor_leave_them_unset() -> None:
    """담당자·Vendor가 없으면 조건에도 없다.

    테스트 코드: DSH-012
    """
    # given: 연도만 있는 조건
    criteria = DashboardCriteria(period=ForecastPeriod(year=2026))

    # when: Status 조건과 연도 조건을 만든다
    status = criteria.status_query()
    year = criteria.year_query()

    # then: 담당자·Vendor가 비어 있다
    assert status == DealQuery(year=2026, forecast_outcome=ForecastOutcomeFilter.NOT_LOST)
    assert year == DealQuery(year=2026)


def test_overdue_and_stale_queries_ignore_period() -> None:
    """기한초과·미업데이트 조건은 기간을 무시하고 담당자·Vendor만 따른다.

    테스트 코드: DSH-016
    """
    # given: 2025년 Q2, 담당자, Vendor 조건
    criteria = _full()

    # when: 기한초과·미업데이트 조건을 만든다
    overdue = criteria.overdue_query(BASIS)
    stale = criteria.stale_query(BASIS)

    # then: 연도·분기·월·outcome이 없고 담당자·Vendor·판정 기준만 있다
    for query in (overdue, stale):
        assert (query.year, query.quarters, query.month) == (None, None, None)
        assert (query.owner_user_id, query.vendor_id) == (OWNER, VENDOR)
        assert query.risk_basis == BASIS
        assert query.forecast_outcome is None
    assert (overdue.overdue, overdue.stale) == (True, False)
    assert (stale.overdue, stale.stale) == (False, True)


def test_closing_quarter_query_uses_today_quarter() -> None:
    """이번 분기 조건은 업무 날짜의 연·분기와 Open outcome이다.

    테스트 코드: DSH-018
    """
    # given: 2025년 Q2 조건과 업무 날짜 2026-08-15
    criteria = _full()

    # when: 이번 분기 조건을 만든다
    query = criteria.closing_quarter_query(date(2026, 8, 15))

    # then: 2026년 Q3, 담당자·Vendor, Open outcome이다
    assert (query.year, query.quarters, query.month) == (2026, frozenset({3}), None)
    assert (query.owner_user_id, query.vendor_id) == (OWNER, VENDOR)
    assert query.forecast_outcome is ForecastOutcomeFilter.OPEN


def test_closing_month_query_uses_today_month() -> None:
    """이번 달 조건은 업무 날짜의 연·월과 Open outcome이다.

    테스트 코드: DSH-018
    """
    # given: 2025년 Q2 조건과 업무 날짜 2026-08-15
    criteria = _full()

    # when: 이번 달 조건을 만든다
    query = criteria.closing_month_query(date(2026, 8, 15))

    # then: 2026년 8월, 담당자·Vendor, Open outcome이다
    assert (query.year, query.quarters, query.month) == (2026, None, 8)
    assert (query.owner_user_id, query.vendor_id) == (OWNER, VENDOR)
    assert query.forecast_outcome is ForecastOutcomeFilter.OPEN


def test_closing_queries_ignore_the_selected_period() -> None:
    """이번 달·이번 분기 조건은 고른 기간을 무시한다.

    테스트 코드: DSH-018
    """
    # given: 2020년 Q1을 고른 조건
    criteria = DashboardCriteria(period=ForecastPeriod(year=2020, quarters=frozenset({1})))

    # when: 업무 날짜 2026-10-23의 이번 분기·이번 달 조건을 만든다
    quarter_query = criteria.closing_quarter_query(TODAY)
    month_query = criteria.closing_month_query(TODAY)

    # then: 연도는 2026이다
    assert quarter_query.year == 2026
    assert month_query.year == 2026


@pytest.mark.parametrize(
    ("today", "year", "quarter", "month"),
    [
        (date(2026, 12, 31), 2026, 4, 12),
        (date(2027, 1, 1), 2027, 1, 1),
    ],
)
def test_closing_queries_on_new_year_day_use_new_year(
    today: date, year: int, quarter: int, month: int
) -> None:
    """업무 날짜가 12-31이면 12월·Q4, 01-01이면 새해 1월·Q1 조건이다.

    테스트 코드: DSH-019
    """
    # given: 2026년 조건
    criteria = DashboardCriteria(period=ForecastPeriod(year=2026))

    # when: 그날의 이번 분기·이번 달 조건을 만든다
    quarter_query = criteria.closing_quarter_query(today)
    month_query = criteria.closing_month_query(today)

    # then: 업무 날짜의 연·분기·월이다
    assert (quarter_query.year, quarter_query.quarters) == (year, frozenset({quarter}))
    assert (month_query.year, month_query.month) == (year, month)


def test_criteria_with_month_raises() -> None:
    """Dashboard 조건은 월 단위 기간을 받지 않는다.

    BDD 밖: 화면·API가 월을 보내지 않으므로(DSH-R2) 도메인 조건 쪽 방어를 확인한다.
    """
    # when·then: 월이 있는 기간으로 조건을 만들면 ValueError다
    with pytest.raises(ValueError, match=r"."):
        DashboardCriteria(period=ForecastPeriod(year=2026, month=3))


def test_chosen_quarters_reach_the_status_open_and_forecast_conditions() -> None:
    """고른 분기는 Status·Open·Forecast 조건에 전달된다.

    테스트 코드: DSH-009
    """
    # given: Q1·Q3를 고른 조건
    criteria = DashboardCriteria(
        period=ForecastPeriod(year=2026, quarters=frozenset({1, 3})), owner_user_id=OWNER
    )

    # when: 세 조건을 만든다
    status = criteria.status_query()
    open_ = criteria.open_query()
    forecast = criteria.forecast_criteria().to_deal_query()

    # then: 모두 Q1·Q3를 가진다
    assert status.quarters == frozenset({1, 3})
    assert open_.quarters == frozenset({1, 3})
    assert forecast.quarters == frozenset({1, 3})


def test_year_overdue_stale_and_closing_month_queries_ignore_chosen_quarters() -> None:
    """분기 행·기한초과·미업데이트·이번 달 조건은 고른 분기를 따르지 않는다.

    테스트 코드: DSH-014, DSH-016
    """
    # given: Q1·Q3를 고른 조건
    criteria = DashboardCriteria(period=ForecastPeriod(year=2026, quarters=frozenset({1, 3})))

    # when: 각 조건을 만든다
    year = criteria.year_query()
    overdue = criteria.overdue_query(BASIS)
    stale = criteria.stale_query(BASIS)
    month = criteria.closing_month_query(TODAY)

    # then: 어느 것도 분기 조건이 없다
    assert year.quarters is None
    assert overdue.quarters is None
    assert stale.quarters is None
    assert month.quarters is None


def test_closing_quarter_query_is_todays_single_quarter_whatever_is_chosen() -> None:
    """이번 분기 조건은 무엇을 골랐든 업무 날짜의 분기 하나다.

    테스트 코드: DSH-018
    """
    # given: Q1·Q2를 고른 조건
    criteria = DashboardCriteria(period=ForecastPeriod(year=2026, quarters=frozenset({1, 2})))

    # when: 업무 날짜 2026-08-15의 이번 분기 조건을 만든다
    query = criteria.closing_quarter_query(date(2026, 8, 15))

    # then: Q3 하나다
    assert query.quarters == frozenset({3})
