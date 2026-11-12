"""ForecastCriteria.to_deal_query: 원장(Deal 목록)과 같은 조건 객체로 변환한다."""

from app.application.ports.deal_repository import DealQuery
from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.forecast.period import ForecastPeriod
from app.domain.vendor.values import VendorId
from tests.support.ids import new_id
from tests.support.user_ids import uid


def test_criteria_maps_to_same_deal_query_conditions() -> None:
    """기준은 원장(Deal 목록)과 같은 연·분기·담당자·Vendor 조건으로 바뀐다"""
    # given: Q4·담당자·Vendor 조건의 기준
    vendor_id = VendorId(new_id())
    owner = uid("crit-owner")
    criteria = ForecastCriteria(
        period=ForecastPeriod(year=2026, quarters=frozenset({4})),
        owner_user_id=owner,
        vendor_id=vendor_id,
    )

    # when: Deal 조회 조건으로 바꾼다
    query = criteria.to_deal_query()

    # then: 연·분기·담당자·Vendor가 그대로다
    assert (query.year, query.quarters, query.month) == (2026, frozenset({4}), None)
    assert query.owner_user_id == owner
    assert query.vendor_id == vendor_id


def test_month_period_maps_to_the_month_condition() -> None:
    """월 기간은 월 조건으로 바뀐다"""
    # when: 2026년 3월 기준을 Deal 조회 조건으로 바꾼다
    query = ForecastCriteria(period=ForecastPeriod(year=2026, month=3)).to_deal_query()

    # then: 월 조건이고 분기·담당자·Vendor는 없다
    assert (query.year, query.quarters, query.month) == (2026, None, 3)
    assert query.owner_user_id is None
    assert query.vendor_id is None


def test_year_only_period_maps_to_a_year_only_query() -> None:
    """연도만 있는 기간은 연도만 있는 조회 조건이 된다"""
    # when: 연도만 있는 기준을 바꾼다
    query = ForecastCriteria(period=ForecastPeriod(year=2026)).to_deal_query()

    # then: 연도만 있는 조회 조건이다
    assert query == DealQuery(year=2026)


def test_the_deal_query_window_equals_the_forecast_period_range() -> None:
    """조회 조건의 날짜 범위는 Forecast 기간 범위와 같다"""
    # given: 윤년 2028년 2월 기간
    period = ForecastPeriod(year=2028, month=2)

    # when: 조회 조건의 날짜 범위를 구한다
    window = ForecastCriteria(period=period).to_deal_query().revenue_window()

    # then: 기간의 날짜 범위와 같다
    assert window == period.date_range()


def test_chosen_quarters_map_to_the_deal_query_quarters() -> None:
    """고른 분기들은 조회 조건의 분기로 바뀐다"""
    # when: Q1·Q3 기준을 바꾼다
    query = ForecastCriteria(
        period=ForecastPeriod(year=2026, quarters=frozenset({1, 3}))
    ).to_deal_query()

    # then: 분기 집합이 Q1·Q3다
    assert query.quarters == frozenset({1, 3})
    assert query.revenue_quarters() == frozenset({1, 3})
