"""업무일 계산(Q1 변경): Deal code의 날짜는 프로세스(OS) 로컬 시간대의 달력 날짜다(AC-03).

실행 머신에 흔들리지 않도록 테스트가 로컬 시간대(TZ)를 고정한다.
"""

from datetime import UTC, date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.domain.common.business_date import business_date

if TYPE_CHECKING:
    from collections.abc import Callable


class TestLocalTimeZoneIsSeoul:
    def test_utc_afternoon_after_1500_is_already_the_next_day(
        self, local_tz: Callable[[str], None]
    ) -> None:
        local_tz("Asia/Seoul")

        assert business_date(datetime(2026, 10, 15, 15, 30, tzinfo=UTC)) == date(2026, 10, 16)

    def test_utc_1500_exactly_is_midnight_of_the_next_day(
        self, local_tz: Callable[[str], None]
    ) -> None:
        local_tz("Asia/Seoul")

        assert business_date(datetime(2026, 10, 15, 15, 0, tzinfo=UTC)) == date(2026, 10, 16)

    def test_utc_1459_is_still_the_same_day(self, local_tz: Callable[[str], None]) -> None:
        local_tz("Asia/Seoul")

        assert business_date(datetime(2026, 10, 15, 14, 59, tzinfo=UTC)) == date(2026, 10, 15)

    def test_another_offset_is_converted_to_local_time_first(
        self, local_tz: Callable[[str], None]
    ) -> None:
        local_tz("Asia/Seoul")
        evening = datetime(2026, 10, 15, 20, 0, tzinfo=timezone(timedelta(hours=-4)))

        assert business_date(evening) == date(2026, 10, 16)  # 00:00Z+1 -> 09:00 로컬

    def test_year_end_rolls_over(self, local_tz: Callable[[str], None]) -> None:
        local_tz("Asia/Seoul")

        assert business_date(datetime(2026, 12, 31, 15, 0, tzinfo=UTC)) == date(2027, 1, 1)


class TestLocalTimeZoneIsUtc:
    def test_utc_afternoon_after_1500_is_still_the_same_day(
        self, local_tz: Callable[[str], None]
    ) -> None:
        local_tz("UTC")

        assert business_date(datetime(2026, 10, 15, 15, 30, tzinfo=UTC)) == date(2026, 10, 15)

    def test_the_last_minute_of_the_utc_day_keeps_its_date(
        self, local_tz: Callable[[str], None]
    ) -> None:
        local_tz("UTC")

        assert business_date(datetime(2026, 10, 15, 23, 59, tzinfo=UTC)) == date(2026, 10, 15)

    def test_utc_midnight_starts_the_next_day(self, local_tz: Callable[[str], None]) -> None:
        local_tz("UTC")

        assert business_date(datetime(2026, 10, 16, 0, 0, tzinfo=UTC)) == date(2026, 10, 16)

    def test_a_seoul_offset_time_is_converted_to_utc_first(
        self, local_tz: Callable[[str], None]
    ) -> None:
        local_tz("UTC")
        seoul_morning = datetime(2026, 10, 16, 8, 0, tzinfo=timezone(timedelta(hours=9)))

        assert business_date(seoul_morning) == date(2026, 10, 15)  # 23:00Z


def test_a_zone_behind_utc_uses_its_own_calendar(local_tz: Callable[[str], None]) -> None:
    local_tz("America/New_York")  # 10월은 UTC-4

    assert business_date(datetime(2026, 10, 16, 2, 0, tzinfo=UTC)) == date(2026, 10, 15)
