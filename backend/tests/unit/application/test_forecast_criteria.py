"""ForecastCriteria.to_deal_query(P6 R1 AC-6): 원장(Deal 목록)과 같은 조건 객체로 변환한다."""

from app.application.ports.deal_repository import DealQuery
from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.forecast.period import ForecastPeriod
from app.domain.vendor.values import VendorId
from tests.support.ids import new_id
from tests.support.user_ids import uid


def test_criteria_maps_to_same_deal_query_conditions() -> None:
    vendor_id = VendorId(new_id())
    owner = uid("crit-owner")
    criteria = ForecastCriteria(
        period=ForecastPeriod(year=2026, quarter=4), owner_user_id=owner, vendor_id=vendor_id
    )

    query = criteria.to_deal_query()

    assert (query.year, query.quarter, query.month) == (2026, 4, None)
    assert query.owner_user_id == owner
    assert query.vendor_id == vendor_id


def test_month_period_maps_to_the_month_condition() -> None:
    query = ForecastCriteria(period=ForecastPeriod(year=2026, month=3)).to_deal_query()

    assert (query.year, query.quarter, query.month) == (2026, None, 3)
    assert query.owner_user_id is None
    assert query.vendor_id is None


def test_year_only_period_maps_to_a_year_only_query() -> None:
    query = ForecastCriteria(period=ForecastPeriod(year=2026)).to_deal_query()

    assert query == DealQuery(year=2026)


def test_the_deal_query_window_equals_the_forecast_period_range() -> None:
    period = ForecastPeriod(year=2028, month=2)

    window = ForecastCriteria(period=period).to_deal_query().revenue_window()

    assert window == period.date_range()
