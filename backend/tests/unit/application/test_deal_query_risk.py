"""DealQuery의 위험 필터 필드(AC-8, AC-10, AC-11): BANT 조건 폐지, overdue·stale·risk_basis."""

from dataclasses import fields
from datetime import date

from app.application.ports.deal_repository import DealQuery
from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.deal.risk import RiskBasis
from app.domain.forecast.period import ForecastPeriod

BASIS = RiskBasis(today=date(2026, 10, 22), stale_days=14)


def test_the_query_has_no_bant_condition() -> None:
    assert "bant_label_ids" not in {f.name for f in fields(DealQuery)}
    assert not hasattr(DealQuery(), "bant_label_ids")


def test_risk_filters_default_to_no_condition() -> None:
    query = DealQuery()

    assert (query.overdue, query.stale, query.risk_basis) == (False, False, None)
    assert query.wants_risk() is False


def test_either_flag_makes_the_query_want_risk() -> None:
    assert DealQuery(overdue=True).wants_risk() is True
    assert DealQuery(stale=True).wants_risk() is True


def test_with_risk_basis_fills_the_basis_only_when_a_risk_filter_is_set() -> None:
    plain = DealQuery(keyword="erp")
    assert plain.with_risk_basis(BASIS) is plain

    for flagged in (
        DealQuery(overdue=True),
        DealQuery(stale=True),
        DealQuery(overdue=True, stale=True),
    ):
        filled = flagged.with_risk_basis(BASIS)
        assert filled.risk_basis == BASIS
        assert (filled.overdue, filled.stale) == (flagged.overdue, flagged.stale)


def test_forecast_query_has_no_risk_filter() -> None:
    query = ForecastCriteria(period=ForecastPeriod(year=2026, quarter=4)).to_deal_query()

    assert (query.overdue, query.stale, query.risk_basis) == (False, False, None)
    assert query.wants_risk() is False
