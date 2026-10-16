"""start_of_business_day: 업무 날짜의 시작(OS 로컬 00:00). 수행일 검색의 경계다(AC-15)."""

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from app.domain.common.business_date import business_date, start_of_business_day

if TYPE_CHECKING:
    from collections.abc import Callable


def test_start_of_business_day_is_local_midnight_in_seoul(
    local_tz: Callable[[str], None],
) -> None:
    local_tz("Asia/Seoul")

    start = start_of_business_day(date(2026, 10, 16))

    assert start == datetime(2026, 10, 15, 15, 0, tzinfo=UTC)  # 로컬 00:00 = 전날 15:00Z


def test_start_of_business_day_is_local_midnight_in_utc(local_tz: Callable[[str], None]) -> None:
    local_tz("UTC")

    assert start_of_business_day(date(2026, 10, 16)) == datetime(2026, 10, 16, 0, 0, tzinfo=UTC)


def test_the_result_is_timezone_aware() -> None:
    start = start_of_business_day(date(2026, 10, 16))

    assert start.tzinfo is not None
    assert start.utcoffset() is not None


def test_consecutive_days_are_twenty_four_hours_apart_in_seoul(
    local_tz: Callable[[str], None],
) -> None:
    local_tz("Asia/Seoul")

    today = start_of_business_day(date(2026, 10, 16))
    tomorrow = start_of_business_day(date(2026, 10, 17))

    assert tomorrow - today == timedelta(hours=24)


def test_the_start_moment_belongs_to_its_own_business_date_and_the_one_before_to_the_previous(
    local_tz: Callable[[str], None],
) -> None:
    local_tz("Asia/Seoul")
    start = start_of_business_day(date(2026, 10, 16))

    assert business_date(start) == date(2026, 10, 16)
    assert business_date(start - timedelta(microseconds=1)) == date(2026, 10, 15)
