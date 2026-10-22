"""Dashboard 요약 쿼리 모델 (AC-2): year 필수, 모르는 파라미터(month 포함) 거절, 범위 검증."""

import pytest
from pydantic import ValidationError

from app.application.dashboard.criteria import DashboardCriteria
from app.domain.forecast.period import ForecastPeriod
from app.domain.user.value_objects import UserId
from app.domain.vendor.values import VendorId
from app.web.schemas.dashboard import DashboardSearchParams
from tests.support.ids import new_id


def test_dashboard_params_require_year() -> None:
    with pytest.raises(ValidationError):
        DashboardSearchParams()  # type: ignore[call-arg]


def test_dashboard_params_reject_unknown_param_month() -> None:
    with pytest.raises(ValidationError):
        DashboardSearchParams(year=2026, month=3)  # type: ignore[call-arg]


def test_dashboard_params_reject_any_other_unknown_param() -> None:
    with pytest.raises(ValidationError):
        DashboardSearchParams(year=2026, vendor="SAP")  # type: ignore[call-arg]


@pytest.mark.parametrize("year", [1899, 10000])
def test_dashboard_params_reject_year_outside_the_range(year: int) -> None:
    with pytest.raises(ValidationError):
        DashboardSearchParams(year=year)


@pytest.mark.parametrize("year", [1900, 9999])
def test_dashboard_params_accept_the_year_range_limits(year: int) -> None:
    assert DashboardSearchParams(year=year).year == year


@pytest.mark.parametrize("quarter", [0, 5])
def test_dashboard_params_reject_out_of_range_quarter(quarter: int) -> None:
    with pytest.raises(ValidationError) as caught:
        DashboardSearchParams(year=2026, quarter=quarter)

    assert caught.value.errors()[0]["loc"] == ("quarter",)


def test_a_non_numeric_year_is_a_validation_error() -> None:
    with pytest.raises(ValidationError):
        DashboardSearchParams(year="abc")


def test_to_criteria_carries_period_owner_and_vendor() -> None:
    owner, vendor = UserId(new_id()), VendorId(new_id())

    criteria = DashboardSearchParams(
        year=2026, quarter=4, owner_user_id=owner, vendor_id=vendor
    ).to_criteria()

    assert criteria == DashboardCriteria(
        period=ForecastPeriod(year=2026, quarter=4), owner_user_id=owner, vendor_id=vendor
    )


def test_to_criteria_without_optional_conditions_leaves_them_unset() -> None:
    criteria = DashboardSearchParams(year=2026).to_criteria()

    assert criteria.period == ForecastPeriod(year=2026)
    assert criteria.owner_user_id is None
    assert criteria.vendor_id is None
