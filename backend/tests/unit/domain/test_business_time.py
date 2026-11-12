"""business_time: 시각을 서버 OS 로컬 시간대(업무 시간대) 오프셋으로 바꾼다.

실행 머신에 흔들리지 않도록 테스트가 로컬 시간대(TZ)를 고정한다.
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

from app.domain.common.business_date import business_date, business_time
from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from collections.abc import Callable


def test_utc_moment_becomes_local_offset_same_instant(local_tz: Callable[[str], None]) -> None:
    """업무 시각은 같은 순간을 서버 시간대 오프셋으로 바꾼다.

    테스트 코드: TM-008
    """
    # given: 서버 시간대 Asia/Seoul
    local_tz("Asia/Seoul")
    moment = datetime(2026, 10, 22, 15, 30, tzinfo=UTC)
    # when: 업무 시각을 구한다
    local = business_time(moment)

    # then: 서울 오프셋 시각이고 순간은 같다
    assert local.isoformat() == "2026-10-23T00:30:00+09:00"
    assert local == moment
    assert local.utcoffset() == timedelta(hours=9)


def test_naive_moment_is_rejected() -> None:
    """시간대 없는 시각은 업무 시각 계산에서 거절된다.

    테스트 코드: TM-010
    """
    # when·then: 시간대 없는 시각의 업무 시각을 구한다 → InvalidValueError
    with pytest.raises(InvalidValueError):
        business_time(datetime(2026, 10, 22, 15, 30))


def test_offset_follows_process_timezone(local_tz: Callable[[str], None]) -> None:
    """오프셋은 서버 프로세스 시간대를 따른다(뉴욕 10월 -04:00).

    테스트 코드: TM-009
    """
    # given: 서버 시간대 America/New_York
    local_tz("America/New_York")
    # when: 10월 시각의 업무 시각을 구한다
    local = business_time(datetime(2026, 10, 22, 12, 0, tzinfo=UTC))

    # then: 08:00-04:00
    assert local.isoformat() == "2026-10-22T08:00:00-04:00"


def test_offset_is_chosen_per_moment_across_daylight_saving(
    local_tz: Callable[[str], None],
) -> None:
    """서머타임 시간대에서는 시각마다 그 순간의 오프셋을 쓴다.

    테스트 코드: TM-009
    """
    # given: 서버 시간대 America/New_York
    local_tz("America/New_York")
    # when: 7월과 12월 시각의 업무 시각을 구한다
    summer = business_time(datetime(2026, 7, 1, 12, 0, tzinfo=UTC))
    winter = business_time(datetime(2026, 12, 1, 12, 0, tzinfo=UTC))

    # then: 각각 -04:00, -05:00
    assert summer.utcoffset() == timedelta(hours=-4)
    assert winter.utcoffset() == timedelta(hours=-5)


def test_other_offset_input_is_converted_to_local(local_tz: Callable[[str], None]) -> None:
    """다른 오프셋으로 들어온 시각도 서버 시간대로 바꾼다.

    테스트 코드: TM-008
    """
    # given: 서버 시간대 Asia/Seoul, -04:00 오프셋 입력
    local_tz("Asia/Seoul")
    moment = datetime(2026, 10, 22, 20, 0, tzinfo=timezone(timedelta(hours=-4)))

    # when: 업무 시각으로 바꾼다
    actual = business_time(moment).isoformat()
    # then: 서울 시각이다
    assert actual == "2026-10-23T09:00:00+09:00"


def test_microseconds_are_kept(local_tz: Callable[[str], None]) -> None:
    """업무 시각은 마이크로초를 유지한다.

    테스트 코드: TM-008
    """
    # given: 서버 시간대 Asia/Seoul
    local_tz("Asia/Seoul")
    # when: 마이크로초가 있는 시각의 업무 시각을 구한다
    local = business_time(datetime(2026, 10, 22, 15, 30, 1, 123456, tzinfo=UTC))

    # then: 마이크로초가 그대로다
    assert local.isoformat() == "2026-10-23T00:30:01.123456+09:00"


def test_business_date_equals_the_date_of_business_time(local_tz: Callable[[str], None]) -> None:
    """업무 날짜는 업무 시각의 날짜 부분과 같다.

    테스트 코드: TM-012
    """
    # given: 서버 시간대 Asia/Seoul, 연말 UTC 15:00
    local_tz("Asia/Seoul")
    moment = datetime(2026, 12, 31, 15, 0, tzinfo=UTC)

    # when: 업무 날짜와 업무 시각을 구한다
    actual = business_time(moment).date()
    # then: 업무 날짜가 업무 시각의 날짜와 같다
    assert business_date(moment) == actual
