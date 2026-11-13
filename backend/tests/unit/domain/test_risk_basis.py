"""RiskBasis.stale_before: 목록 미업데이트 필터의 경계 날짜가 compute_risk와 같은 판정을 만든다.

날짜끼리 비교하므로 시간대 변환이 없다(RK-R5, `last_updated_on < stale_before`이면 미업데이트).
"""

from datetime import date, timedelta

import pytest

from app.domain.deal.risk import Risk, RiskBasis, compute_risk

TODAY = date(2026, 10, 22)


def _flagged_stale(day: date, stale_days: int) -> bool:
    risk = compute_risk(
        forecast_key="pipeline",
        due_date=None,
        last_updated_on=day,
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
    last_stale = date(2026, 10, 8)  # TODAY - 14일
    first_fresh = date(2026, 10, 9)  # TODAY - 13일

    # when: 경계 직전 날짜와 경계 날짜를 stale_before와 compute_risk로 판정한다
    # then: 마지막 stale 날짜는 둘 다 미업데이트, 첫 정상 날짜는 둘 다 정상이다
    assert basis.stale_before() == first_fresh
    assert last_stale < basis.stale_before()
    assert _flagged_stale(last_stale, 14) is True
    assert not first_fresh < basis.stale_before()
    assert _flagged_stale(first_fresh, 14) is False


def test_stale_before_with_one_day_means_before_today() -> None:
    """기준 1일이면 stale_before는 오늘 날짜다(어제까지 미업데이트).

    테스트 코드: RK-031
    """
    # given: 오늘 10-22, 기준 1일이다
    basis = RiskBasis(today=TODAY, stale_days=1)

    # when: stale_before를 구한다
    # then: 오늘이며 어제는 앞이고 오늘은 앞이 아니다
    assert basis.stale_before() == TODAY
    assert TODAY - timedelta(days=1) < basis.stale_before()
    assert not basis.stale_before() > TODAY


@pytest.mark.parametrize("stale_days", [1, 14, 365])
def test_stale_before_agrees_with_compute_risk_for_each_offset(stale_days: int) -> None:
    """기준 1·14·365일 모두 날짜마다 stale_before와 compute_risk가 같은 판정을 낸다.

    테스트 코드: RK-031
    """
    # given: 기준 일수별 판정 기준이다
    basis = RiskBasis(today=TODAY, stale_days=stale_days)
    # when·then: 경과일별로 stale_before와 compute_risk를 비교한다 → 모든 날짜에서 두 판정이 같다
    for elapsed in range(stale_days + 2):
        day = TODAY - timedelta(days=elapsed)
        assert (day < basis.stale_before()) == _flagged_stale(day, stale_days), elapsed


@pytest.mark.parametrize("stale_days", [0, -1])
def test_risk_basis_rejects_stale_days_below_one(stale_days: int) -> None:
    """기준 일수가 1 미만이면 프로그래밍 오류(ValueError)다.

    테스트 코드: RK-031
    """
    # when·then: 0 이하 기준으로 만든다 → ValueError다
    with pytest.raises(ValueError):  # noqa: PT011 - 프로그래밍 오류(ValueError)
        RiskBasis(today=TODAY, stale_days=stale_days)
