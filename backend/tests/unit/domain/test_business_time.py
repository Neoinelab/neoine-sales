"""business_time: 시각을 서버 OS 로컬 시간대(업무 시간대) 오프셋으로 바꾼다(서버 시간 통일 AC1·2).

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
    local_tz("Asia/Seoul")
    moment = datetime(2026, 10, 22, 15, 30, tzinfo=UTC)

    local = business_time(moment)

    assert local.isoformat() == "2026-10-23T00:30:00+09:00"
    assert local == moment  # 순간은 바뀌지 않는다
    assert local.utcoffset() == timedelta(hours=9)


def test_naive_moment_is_rejected() -> None:
    with pytest.raises(InvalidValueError):
        business_time(datetime(2026, 10, 22, 15, 30))


def test_offset_follows_process_timezone(local_tz: Callable[[str], None]) -> None:
    local_tz("America/New_York")  # 10월은 UTC-4(서머타임)

    local = business_time(datetime(2026, 10, 22, 12, 0, tzinfo=UTC))

    assert local.isoformat() == "2026-10-22T08:00:00-04:00"


def test_offset_is_chosen_per_moment_across_daylight_saving(
    local_tz: Callable[[str], None],
) -> None:
    local_tz("America/New_York")

    summer = business_time(datetime(2026, 7, 1, 12, 0, tzinfo=UTC))
    winter = business_time(datetime(2026, 12, 1, 12, 0, tzinfo=UTC))

    assert summer.utcoffset() == timedelta(hours=-4)
    assert winter.utcoffset() == timedelta(hours=-5)


def test_other_offset_input_is_converted_to_local(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")
    moment = datetime(2026, 10, 22, 20, 0, tzinfo=timezone(timedelta(hours=-4)))

    assert business_time(moment).isoformat() == "2026-10-23T09:00:00+09:00"


def test_microseconds_are_kept(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")

    local = business_time(datetime(2026, 10, 22, 15, 30, 1, 123456, tzinfo=UTC))

    assert local.isoformat() == "2026-10-23T00:30:01.123456+09:00"


def test_business_date_equals_the_date_of_business_time(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")
    moment = datetime(2026, 12, 31, 15, 0, tzinfo=UTC)

    assert business_date(moment) == business_time(moment).date()
