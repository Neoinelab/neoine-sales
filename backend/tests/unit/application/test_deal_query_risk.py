"""DealQuery의 위험 필터 필드: BANT 조건 폐지, overdue·stale·risk_basis."""

from dataclasses import fields
from datetime import date

from app.application.ports.deal_repository import DealQuery
from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.deal.risk import RiskBasis
from app.domain.forecast.period import ForecastPeriod

BASIS = RiskBasis(today=date(2026, 10, 22), stale_days=14)


def test_the_query_has_no_bant_condition() -> None:
    """DealQuery에는 BANT 조건이 없다."""
    # when: 필드 이름을 살핀다
    assert "bant_label_ids" not in {f.name for f in fields(DealQuery)}
    # then: bant_label_ids 필드가 없다
    assert not hasattr(DealQuery(), "bant_label_ids")


def test_risk_filters_default_to_no_condition() -> None:
    """경고 필터는 기본이 꺼짐이고 경고 기준도 없다.

    테스트 코드: RK-029
    """
    # when: 조건 없이 DealQuery를 만든다
    query = DealQuery()

    # then: overdue·stale이 꺼져 있고 경고 판정 기준이 없으며 경고 조건을 원하지 않는다
    assert (query.overdue, query.stale, query.risk_basis) == (False, False, None)
    assert query.wants_risk() is False


def test_either_flag_makes_the_query_want_risk() -> None:
    """overdue나 stale 중 하나만 켜도 경고 조건을 원한다.

    테스트 코드: RK-027, RK-028
    """
    # when: 한 필터만 켠다
    assert DealQuery(overdue=True).wants_risk() is True
    # then: wants_risk가 true다
    assert DealQuery(stale=True).wants_risk() is True


def test_with_risk_basis_fills_the_basis_only_when_a_risk_filter_is_set() -> None:
    """경고 필터가 켜졌을 때만 같은 요청의 판정 기준(오늘·경고 기준)이 채워진다.

    테스트 코드: RK-030
    """
    # given: 오늘 10-22, 기준 14일의 판정 기준이다
    plain = DealQuery(keyword="erp")
    # when: 판정 기준을 채운다
    assert plain.with_risk_basis(BASIS) is plain

    # then: 필터 없는 조건은 그대로이고 필터 있는 조건에는 기준이 채워진다
    for flagged in (
        DealQuery(overdue=True),
        DealQuery(stale=True),
        DealQuery(overdue=True, stale=True),
    ):
        filled = flagged.with_risk_basis(BASIS)
        assert filled.risk_basis == BASIS
        assert (filled.overdue, filled.stale) == (flagged.overdue, flagged.stale)


def test_forecast_query_has_no_risk_filter() -> None:
    """Forecast 조건에서 만든 Deal 조건에는 경고 필터가 없다."""
    # when: Forecast 조건을 Deal 조건으로 바꾼다
    query = ForecastCriteria(
        period=ForecastPeriod(year=2026, quarters=frozenset({4}))
    ).to_deal_query()

    # then: 경고 필터가 꺼져 있다
    assert (query.overdue, query.stale, query.risk_basis) == (False, False, None)
    assert query.wants_risk() is False
