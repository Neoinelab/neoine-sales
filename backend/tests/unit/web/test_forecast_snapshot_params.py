"""Forecast 스냅숏 요약 쿼리 모델: 기간·담당자 조건만 받고 Vendor는 받지 않는다."""

import pytest
from pydantic import ValidationError

from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.common.errors import InvalidValueError
from app.domain.forecast.period import ForecastPeriod
from app.domain.user.value_objects import UserId
from app.web.schemas.forecast import ForecastSnapshotSearchParams
from tests.support.ids import new_id


def test_snapshot_params_reject_vendor_id() -> None:
    """스냅숏 쿼리는 vendor_id를 거절한다"""
    # when: vendor_id를 주고 만든다
    with pytest.raises(ValidationError) as caught:
        ForecastSnapshotSearchParams(year=2026, vendor_id=new_id())  # type: ignore[call-arg]

    # then: 오류 위치가 vendor_id다
    assert caught.value.errors()[0]["loc"] == ("vendor_id",)


def test_snapshot_params_reject_unknown_param() -> None:
    """모르는 파라미터는 거절한다"""
    # when·then: vendor=SAP를 주면 ValidationError다
    with pytest.raises(ValidationError):
        ForecastSnapshotSearchParams(year=2026, vendor="SAP")  # type: ignore[call-arg]


def test_snapshot_params_require_year() -> None:
    """year가 없으면 거절한다"""
    # when·then: year 없이 만들면 ValidationError다
    with pytest.raises(ValidationError):
        ForecastSnapshotSearchParams()  # type: ignore[call-arg]


@pytest.mark.parametrize("quarter", [0, 5])
def test_snapshot_params_reject_a_quarter_outside_one_to_four(quarter: int) -> None:
    """Quarter가 1~4 밖이면 거절한다"""
    # when: 범위 밖 Quarter로 만든다
    with pytest.raises(ValidationError) as caught:
        ForecastSnapshotSearchParams(year=2026, quarter=quarter)

    # then: 오류 위치가 quarter다
    assert caught.value.errors()[0]["loc"] == ("quarter",)


@pytest.mark.parametrize("month", [0, 13])
def test_snapshot_params_reject_a_month_outside_one_to_twelve(month: int) -> None:
    """월이 1~12 밖이면 거절한다"""
    # when: 범위 밖 월로 만든다
    with pytest.raises(ValidationError) as caught:
        ForecastSnapshotSearchParams(year=2026, month=month)

    # then: 오류 위치가 month다
    assert caught.value.errors()[0]["loc"] == ("month",)


def test_snapshot_to_criteria_carries_period_and_owner_without_vendor() -> None:
    """스냅숏 기준 변환은 기간·담당자를 담고 Vendor는 없다"""
    # given: 담당자 id
    owner = UserId(new_id())

    # when: Q3 쿼리를 기준으로 바꾼다
    criteria = ForecastSnapshotSearchParams(year=2026, quarter=3, owner_user_id=owner).to_criteria()

    # then: Q3 기간과 담당자만 담기고 Vendor는 없다
    assert criteria == ForecastCriteria(
        period=ForecastPeriod(year=2026, quarters=frozenset({3})),
        owner_user_id=owner,
        vendor_id=None,
    )


def test_snapshot_quarter_and_month_together_are_a_domain_error() -> None:
    """Quarter와 월 동시는 기준 변환에서 InvalidValueError다"""
    # given: quarter=1&month=1(스키마는 통과)
    params = ForecastSnapshotSearchParams(year=2026, quarter=1, month=1)  # 스키마는 통과

    # when·then: 기준으로 바꾸면 InvalidValueError다
    with pytest.raises(InvalidValueError):
        params.to_criteria()
