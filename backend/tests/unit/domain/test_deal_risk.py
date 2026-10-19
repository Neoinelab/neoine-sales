"""Deal Risk 계산(P3 AC-01~04, R03·R04·R06): 기한초과, 미업데이트, 종결 제외.

"오늘"과 `last_updated_at`의 날짜는 OS 로컬 시간대의 달력 날짜다. 실행 머신에 흔들리지 않도록
테스트가 시간대(TZ)를 고정한다.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal.risk import Risk, compute_risk, is_closed_forecast

if TYPE_CHECKING:
    from collections.abc import Callable

TODAY = date(2026, 10, 20)
STALE_DAYS = 14
FRESH = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)  # 1일 전
STALE_BOUNDARY = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)  # 14일 전
ONE_DAY_BEFORE_BOUNDARY = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)  # 13일 전


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


def _risk(
    *,
    forecast_key: str = "pipeline",
    due_date: date | None = None,
    last_updated_at: datetime = FRESH,
    today: date = TODAY,
    stale_days: int = STALE_DAYS,
) -> Risk | None:
    return compute_risk(
        forecast_key=forecast_key,
        due_date=due_date,
        last_updated_at=last_updated_at,
        today=today,
        stale_days=stale_days,
    )


def test_due_today_is_not_overdue() -> None:
    assert _risk(due_date=TODAY) is None


def test_due_yesterday_is_overdue() -> None:
    assert _risk(due_date=date(2026, 10, 19)) is Risk.OVERDUE


def test_due_tomorrow_is_not_overdue() -> None:
    assert _risk(due_date=date(2026, 10, 21)) is None


def test_no_action_is_not_overdue() -> None:
    assert _risk(due_date=None) is None


def test_stale_from_exactly_stale_days() -> None:
    assert _risk(last_updated_at=STALE_BOUNDARY) is Risk.STALE


def test_not_stale_one_day_before() -> None:
    assert _risk(last_updated_at=ONE_DAY_BEFORE_BOUNDARY) is None


def test_stale_far_beyond_the_boundary() -> None:
    assert _risk(last_updated_at=datetime(2026, 1, 1, tzinfo=UTC)) is Risk.STALE


def test_overdue_and_stale_is_overdue_stale() -> None:
    risk = _risk(due_date=date(2026, 10, 1), last_updated_at=STALE_BOUNDARY)

    assert risk is Risk.OVERDUE_STALE


def test_overdue_only_is_not_marked_stale() -> None:
    assert _risk(due_date=date(2026, 10, 1), last_updated_at=FRESH) is Risk.OVERDUE


@pytest.mark.parametrize("forecast_key", ["won", "lost"])
def test_won_and_lost_have_no_risk(forecast_key: str) -> None:
    risk = _risk(
        forecast_key=forecast_key,
        due_date=date(2026, 10, 1),
        last_updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert risk is None


@pytest.mark.parametrize("forecast_key", ["pipeline", "best", "commit", "upside"])
def test_open_forecasts_keep_their_risk(forecast_key: str) -> None:
    assert _risk(forecast_key=forecast_key, due_date=date(2026, 10, 1)) is Risk.OVERDUE


@pytest.mark.parametrize(
    ("forecast_key", "closed"),
    [("won", True), ("lost", True), ("pipeline", False), ("commit", False), ("Won", False)],
)
def test_closed_forecast_is_decided_by_key(forecast_key: str, closed: bool) -> None:
    assert is_closed_forecast(forecast_key) is closed


def test_custom_stale_days_is_used() -> None:
    week_old = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)

    assert _risk(last_updated_at=week_old, stale_days=7) is Risk.STALE
    assert _risk(last_updated_at=week_old, stale_days=8) is None


def test_stale_days_of_one_makes_yesterday_stale_and_today_fresh() -> None:
    assert _risk(last_updated_at=FRESH, stale_days=1) is Risk.STALE
    assert _risk(last_updated_at=datetime(2026, 10, 20, 1, 0, tzinfo=UTC), stale_days=1) is None


def test_today_uses_local_calendar_date() -> None:
    # 2026-10-15 15:30Z = Seoul 10-16 00:30. 오늘 10-29와의 로컬 차이는 13일(UTC 날짜로는 14일)이다.
    updated = datetime(2026, 10, 15, 15, 30, tzinfo=UTC)

    assert _risk(last_updated_at=updated, today=date(2026, 10, 29)) is None
    assert _risk(last_updated_at=updated, today=date(2026, 10, 30)) is Risk.STALE


def test_updated_at_is_converted_to_the_local_zone_before_counting(
    local_tz: Callable[[str], None],
) -> None:
    updated = datetime(2026, 10, 15, 15, 30, tzinfo=UTC)
    local_tz("UTC")

    assert _risk(last_updated_at=updated, today=date(2026, 10, 29)) is Risk.STALE


def test_naive_last_updated_at_is_rejected() -> None:
    with pytest.raises(InvalidValueError, match="시간대"):
        _risk(last_updated_at=datetime(2026, 10, 1, 9, 0))
