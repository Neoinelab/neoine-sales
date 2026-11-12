"""RiskBasis.stale_before: 목록 미업데이트 필터의 경계 시각이 compute_risk와 같은 판정을 만든다.

(T-1~T-4) 업무 날짜는 OS 로컬 시간대 기준이라 테스트가 시간대를 Asia/Seoul로 고정한다.
"""

from datetime import date, datetime, time
from typing import TYPE_CHECKING

import pytest

from app.domain.common.business_date import start_of_business_day
from app.domain.deal.risk import Risk, RiskBasis, compute_risk

if TYPE_CHECKING:
    from collections.abc import Callable

TODAY = date(2026, 10, 22)


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


def _local(day: date, at: time) -> datetime:
    return datetime.combine(day, at).astimezone()


def _flagged_stale(moment: datetime, stale_days: int) -> bool:
    risk = compute_risk(
        forecast_key="pipeline",
        due_date=None,
        last_updated_at=moment,
        today=TODAY,
        stale_days=stale_days,
    )
    return risk in {Risk.STALE, Risk.OVERDUE_STALE}


def test_stale_before_matches_compute_risk_at_the_day_boundary() -> None:
    """미업데이트 필터의 날짜 경계가 compute_risk와 일치한다.

    테스트 코드: RK-031
    """
    # given: 오늘 10-22, 기준 14일이다
    basis = RiskBasis(today=TODAY, stale_days=14)
    last_stale = _local(date(2026, 10, 8), time(23, 59, 59))  # TODAY - 14일
    first_fresh = _local(date(2026, 10, 9), time(0, 0, 0))  # TODAY - 13일

    # when: 경계 직전 순간과 경계 순간을 stale_before와 compute_risk로 판정한다
    assert last_stale < basis.stale_before()
    assert _flagged_stale(last_stale, 14) is True
    # then: 마지막 stale 순간은 둘 다 미업데이트, 첫 정상 순간은 둘 다 정상이다
    assert not first_fresh < basis.stale_before()
    assert _flagged_stale(first_fresh, 14) is False


def test_stale_before_with_one_day_means_before_today() -> None:
    """기준 1일이면 stale_before는 오늘 시작 시각이다.

    테스트 코드: RK-031
    """
    # given: 오늘 10-22, 기준 1일이다
    basis = RiskBasis(today=TODAY, stale_days=1)

    # when: stale_before를 구한다
    assert basis.stale_before() == start_of_business_day(TODAY)
    # then: 어제 23:59는 앞이고 오늘 00:00은 앞이 아니다
    assert _local(date(2026, 10, 21), time(23, 59)) < basis.stale_before()
    assert not _local(TODAY, time(0, 0)) < basis.stale_before()


@pytest.mark.parametrize("stale_days", [1, 14, 365])
def test_stale_before_agrees_with_compute_risk_for_each_offset(stale_days: int) -> None:
    """기준 1·14·365일 모두 날짜·시각마다 stale_before와 compute_risk가 같은 판정을 낸다.

    테스트 코드: RK-031
    """
    # given: 기준 일수별 판정 기준이다
    basis = RiskBasis(today=TODAY, stale_days=stale_days)
    # when·then: 경과일과 시각별로 stale_before와 compute_risk를 비교한다
    #   → 모든 순간에서 두 판정이 같다
    for elapsed in range(stale_days + 2):
        day = date.fromordinal(TODAY.toordinal() - elapsed)
        for at in (time(0, 0), time(12, 0), time(23, 59, 59)):
            moment = _local(day, at)
            assert (moment < basis.stale_before()) == _flagged_stale(moment, stale_days), (
                elapsed,
                at,
            )


@pytest.mark.parametrize("stale_days", [0, -1])
def test_risk_basis_rejects_stale_days_below_one(stale_days: int) -> None:
    """기준 일수가 1 미만이면 프로그래밍 오류(ValueError)다.

    테스트 코드: RK-031
    """
    # when·then: 0 이하 기준으로 만든다 → ValueError다
    with pytest.raises(ValueError):  # noqa: PT011 - 프로그래밍 오류(ValueError)
        RiskBasis(today=TODAY, stale_days=stale_days)
