"""DashboardCriteria (Dashboard AC-4·6·7): 각 숫자의 조건을 정의하는 단일 출처.

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
        period=ForecastPeriod(year=2025, quarter=2), owner_user_id=OWNER, vendor_id=VENDOR
    )


def test_forecast_criteria_carries_period_owner_and_vendor() -> None:
    assert _full().forecast_criteria() == ForecastCriteria(
        period=ForecastPeriod(year=2025, quarter=2), owner_user_id=OWNER, vendor_id=VENDOR
    )


def test_status_query_excludes_lost_and_keeps_period_owner_vendor() -> None:
    query = _full().status_query()

    assert (query.year, query.quarter, query.month) == (2025, 2, None)
    assert query.owner_user_id == OWNER
    assert query.vendor_id == VENDOR
    assert query.forecast_outcome is ForecastOutcomeFilter.NOT_LOST
    assert (query.status_key, query.forecast_key) == (None, None)
    assert (query.overdue, query.stale) == (False, False)


def test_open_query_selects_open_outcome() -> None:
    query = _full().open_query()

    assert (query.year, query.quarter) == (2025, 2)
    assert (query.owner_user_id, query.vendor_id) == (OWNER, VENDOR)
    assert query.forecast_outcome is ForecastOutcomeFilter.OPEN


def test_year_query_drops_quarter() -> None:
    query = _full().year_query()

    assert (query.year, query.quarter, query.month) == (2025, None, None)
    assert (query.owner_user_id, query.vendor_id) == (OWNER, VENDOR)
    assert query.forecast_outcome is None


def test_queries_without_owner_and_vendor_leave_them_unset() -> None:
    criteria = DashboardCriteria(period=ForecastPeriod(year=2026))

    assert criteria.status_query() == DealQuery(
        year=2026, forecast_outcome=ForecastOutcomeFilter.NOT_LOST
    )
    assert criteria.year_query() == DealQuery(year=2026)


def test_overdue_and_stale_queries_ignore_period() -> None:
    overdue = _full().overdue_query(BASIS)
    stale = _full().stale_query(BASIS)

    for query in (overdue, stale):
        assert (query.year, query.quarter, query.month) == (None, None, None)
        assert (query.owner_user_id, query.vendor_id) == (OWNER, VENDOR)
        assert query.risk_basis == BASIS
        assert query.forecast_outcome is None
    assert (overdue.overdue, overdue.stale) == (True, False)
    assert (stale.overdue, stale.stale) == (False, True)


def test_closing_quarter_query_uses_today_quarter() -> None:
    query = _full().closing_quarter_query(date(2026, 8, 15))

    assert (query.year, query.quarter, query.month) == (2026, 3, None)
    assert (query.owner_user_id, query.vendor_id) == (OWNER, VENDOR)
    assert query.forecast_outcome is ForecastOutcomeFilter.OPEN


def test_closing_month_query_uses_today_month() -> None:
    query = _full().closing_month_query(date(2026, 8, 15))

    assert (query.year, query.quarter, query.month) == (2026, None, 8)
    assert (query.owner_user_id, query.vendor_id) == (OWNER, VENDOR)
    assert query.forecast_outcome is ForecastOutcomeFilter.OPEN


def test_closing_queries_ignore_the_selected_period() -> None:
    criteria = DashboardCriteria(period=ForecastPeriod(year=2020, quarter=1))

    assert criteria.closing_quarter_query(TODAY).year == 2026
    assert criteria.closing_month_query(TODAY).year == 2026


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
    criteria = DashboardCriteria(period=ForecastPeriod(year=2026))

    quarter_query = criteria.closing_quarter_query(today)
    month_query = criteria.closing_month_query(today)

    assert (quarter_query.year, quarter_query.quarter) == (year, quarter)
    assert (month_query.year, month_query.month) == (year, month)


def test_criteria_with_month_raises() -> None:
    with pytest.raises(ValueError, match=r"."):
        DashboardCriteria(period=ForecastPeriod(year=2026, month=3))
