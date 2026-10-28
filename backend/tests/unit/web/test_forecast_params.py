"""Forecast 요약 쿼리 모델(P6 R1 AC-1·8): year 필수, 모르는 파라미터 거절, 범위 검증, 기준 변환."""

import re

import pytest
from pydantic import ValidationError

from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.common.errors import InvalidValueError
from app.domain.forecast.period import ForecastPeriod
from app.domain.user.value_objects import UserId
from app.domain.vendor.values import VendorId
from app.web.schemas.forecast import ForecastSearchParams
from tests.support.ids import new_id


def test_forecast_params_require_year() -> None:
    with pytest.raises(ValidationError):
        ForecastSearchParams()  # type: ignore[call-arg]


def test_forecast_params_reject_unknown_param() -> None:
    with pytest.raises(ValidationError):
        ForecastSearchParams(year=2026, vendor="SAP")  # type: ignore[call-arg]


@pytest.mark.parametrize("year", [1899, 10000])
def test_year_outside_the_schema_range_is_a_validation_error(year: int) -> None:
    with pytest.raises(ValidationError):
        ForecastSearchParams(year=year)


@pytest.mark.parametrize("quarter", [0, 5])
def test_quarter_outside_one_to_four_is_a_validation_error(quarter: int) -> None:
    with pytest.raises(ValidationError) as caught:
        ForecastSearchParams(year=2026, quarter=quarter)

    assert caught.value.errors()[0]["loc"] == ("quarter",)
    assert caught.value.errors()[0]["type"] in {"greater_than_equal", "less_than_equal"}


@pytest.mark.parametrize("month", [0, 13])
def test_month_outside_one_to_twelve_is_a_validation_error(month: int) -> None:
    with pytest.raises(ValidationError) as caught:
        ForecastSearchParams(year=2026, month=month)

    assert caught.value.errors()[0]["loc"] == ("month",)
    assert caught.value.errors()[0]["type"] in {"greater_than_equal", "less_than_equal"}


def test_a_non_numeric_year_is_a_validation_error() -> None:
    with pytest.raises(ValidationError):
        ForecastSearchParams(year="abc")


def test_to_criteria_carries_period_owner_and_vendor() -> None:
    owner, vendor = UserId(new_id()), VendorId(new_id())

    criteria = ForecastSearchParams(
        year=2026, quarter=4, owner_user_id=owner, vendor_id=vendor
    ).to_criteria()

    assert criteria == ForecastCriteria(
        period=ForecastPeriod(year=2026, quarters=frozenset({4})),
        owner_user_id=owner,
        vendor_id=vendor,
    )


def test_to_criteria_for_a_month_has_no_quarter() -> None:
    criteria = ForecastSearchParams(year=2026, month=3).to_criteria()

    assert criteria.period == ForecastPeriod(year=2026, month=3)
    assert criteria.owner_user_id is None
    assert criteria.vendor_id is None


def test_quarter_and_month_together_are_a_domain_error_not_a_schema_error() -> None:
    params = ForecastSearchParams(year=2026, quarter=1, month=1)  # 스키마는 통과

    with pytest.raises(
        InvalidValueError, match=re.escape("Quarter와 월은 함께 선택할 수 없습니다.")
    ):
        params.to_criteria()
