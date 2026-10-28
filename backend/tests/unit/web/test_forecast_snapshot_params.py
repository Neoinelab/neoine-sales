"""Forecast 스냅숏 요약 쿼리 모델(P6 R2 AC-17): 기간·담당자 조건만 받고 Vendor는 받지 않는다."""

import pytest
from pydantic import ValidationError

from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.common.errors import InvalidValueError
from app.domain.forecast.period import ForecastPeriod
from app.domain.user.value_objects import UserId
from app.web.schemas.forecast import ForecastSnapshotSearchParams
from tests.support.ids import new_id


def test_snapshot_params_reject_vendor_id() -> None:
    with pytest.raises(ValidationError) as caught:
        ForecastSnapshotSearchParams(year=2026, vendor_id=new_id())  # type: ignore[call-arg]

    assert caught.value.errors()[0]["loc"] == ("vendor_id",)


def test_snapshot_params_reject_unknown_param() -> None:
    with pytest.raises(ValidationError):
        ForecastSnapshotSearchParams(year=2026, vendor="SAP")  # type: ignore[call-arg]


def test_snapshot_params_require_year() -> None:
    with pytest.raises(ValidationError):
        ForecastSnapshotSearchParams()  # type: ignore[call-arg]


@pytest.mark.parametrize("quarter", [0, 5])
def test_snapshot_params_reject_a_quarter_outside_one_to_four(quarter: int) -> None:
    with pytest.raises(ValidationError) as caught:
        ForecastSnapshotSearchParams(year=2026, quarter=quarter)

    assert caught.value.errors()[0]["loc"] == ("quarter",)


@pytest.mark.parametrize("month", [0, 13])
def test_snapshot_params_reject_a_month_outside_one_to_twelve(month: int) -> None:
    with pytest.raises(ValidationError) as caught:
        ForecastSnapshotSearchParams(year=2026, month=month)

    assert caught.value.errors()[0]["loc"] == ("month",)


def test_snapshot_to_criteria_carries_period_and_owner_without_vendor() -> None:
    owner = UserId(new_id())

    criteria = ForecastSnapshotSearchParams(year=2026, quarter=3, owner_user_id=owner).to_criteria()

    assert criteria == ForecastCriteria(
        period=ForecastPeriod(year=2026, quarters=frozenset({3})),
        owner_user_id=owner,
        vendor_id=None,
    )


def test_snapshot_quarter_and_month_together_are_a_domain_error() -> None:
    params = ForecastSnapshotSearchParams(year=2026, quarter=1, month=1)  # 스키마는 통과

    with pytest.raises(InvalidValueError):
        params.to_criteria()
