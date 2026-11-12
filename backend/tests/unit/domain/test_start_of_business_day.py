"""start_of_business_day: 업무 날짜의 시작(OS 로컬 00:00). 날짜 범위 조건의 경계다."""

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from app.domain.common.business_date import business_date, start_of_business_day

if TYPE_CHECKING:
    from collections.abc import Callable


def test_start_of_business_day_is_local_midnight_in_seoul(
    local_tz: Callable[[str], None],
) -> None:
    """업무일 시작은 서울 00:00(전날 15:00Z)이다.

    테스트 코드: TM-013
    """
    # given: 서버 시간대 Asia/Seoul
    local_tz("Asia/Seoul")
    # when: 2026-10-16의 업무일 시작을 구한다
    start = start_of_business_day(date(2026, 10, 16))

    # then: 2026-10-15T15:00Z
    assert start == datetime(2026, 10, 15, 15, 0, tzinfo=UTC)


def test_start_of_business_day_is_local_midnight_in_utc(local_tz: Callable[[str], None]) -> None:
    """서버 시간대가 UTC면 업무일 시작은 UTC 00:00이다.

    테스트 코드: TM-013
    """
    # given: 서버 시간대 UTC
    local_tz("UTC")
    # when: 2026-10-16의 업무일 시작을 구한다
    actual = start_of_business_day(date(2026, 10, 16))
    # then: 2026-10-16T00:00Z다
    assert actual == datetime(2026, 10, 16, 0, 0, tzinfo=UTC)


def test_the_result_is_timezone_aware() -> None:
    """업무일 시작은 시간대가 있는 시각이다.

    테스트 코드: TM-013
    """
    # when: 업무일 시작을 구한다
    start = start_of_business_day(date(2026, 10, 16))

    # then: 오프셋이 있다
    assert start.tzinfo is not None
    assert start.utcoffset() is not None


def test_consecutive_days_are_twenty_four_hours_apart_in_seoul(
    local_tz: Callable[[str], None],
) -> None:
    """연속한 두 날의 시작은 24시간 차이다.

    테스트 코드: TM-013
    """
    # given: 서버 시간대 Asia/Seoul
    local_tz("Asia/Seoul")
    # when: 10-16과 10-17의 업무일 시작을 구한다
    today = start_of_business_day(date(2026, 10, 16))
    tomorrow = start_of_business_day(date(2026, 10, 17))

    # then: 24시간 차이
    assert tomorrow - today == timedelta(hours=24)


def test_the_start_moment_belongs_to_its_own_business_date_and_the_one_before_to_the_previous(
    local_tz: Callable[[str], None],
) -> None:
    """시작 순간은 그 날이고 1마이크로초 전은 전날이다.

    테스트 코드: TM-013
    """
    # given: 서버 시간대 Asia/Seoul, 10-16의 업무일 시작
    local_tz("Asia/Seoul")
    start = start_of_business_day(date(2026, 10, 16))

    # when·then: 시작 순간은 10-16, 1마이크로초 전은 10-15
    assert business_date(start) == date(2026, 10, 16)
    assert business_date(start - timedelta(microseconds=1)) == date(2026, 10, 15)
