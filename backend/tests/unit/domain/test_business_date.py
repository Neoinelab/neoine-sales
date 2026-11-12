"""업무 날짜 계산: 업무 날짜는 프로세스(OS) 로컬 시간대의 달력 날짜다.

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
        """UTC 15시 이후는 서울 기준 다음 날이다.

        테스트 코드: TM-011
        """
        # given: 서버 시간대 Asia/Seoul
        local_tz("Asia/Seoul")
        # when: UTC 10-15 15:30의 업무 날짜를 구한다
        actual = business_date(datetime(2026, 10, 15, 15, 30, tzinfo=UTC))
        # then: 10-16이다
        assert actual == date(2026, 10, 16)

    def test_utc_1500_exactly_is_midnight_of_the_next_day(
        self, local_tz: Callable[[str], None]
    ) -> None:
        """UTC 15:00 정각은 서울 다음 날 00:00이다.

        테스트 코드: TM-011
        """
        # given: 서버 시간대 Asia/Seoul
        local_tz("Asia/Seoul")
        # when: UTC 10-15 15:00의 업무 날짜를 구한다
        actual = business_date(datetime(2026, 10, 15, 15, 0, tzinfo=UTC))
        # then: 10-16이다
        assert actual == date(2026, 10, 16)

    def test_utc_1459_is_still_the_same_day(self, local_tz: Callable[[str], None]) -> None:
        """UTC 14:59는 서울에서 아직 같은 날이다.

        테스트 코드: TM-011
        """
        # given: 서버 시간대 Asia/Seoul
        local_tz("Asia/Seoul")
        # when: UTC 10-15 14:59의 업무 날짜를 구한다
        actual = business_date(datetime(2026, 10, 15, 14, 59, tzinfo=UTC))
        # then: 10-15다
        assert actual == date(2026, 10, 15)

    def test_another_offset_is_converted_to_local_time_first(
        self, local_tz: Callable[[str], None]
    ) -> None:
        """다른 오프셋 시각은 서버 시간대로 먼저 바꾼 뒤 날짜를 정한다.

        테스트 코드: TM-012
        """
        # given: 서버 시간대 Asia/Seoul, -04:00 오프셋의 10-15 20:00
        local_tz("Asia/Seoul")
        evening = datetime(2026, 10, 15, 20, 0, tzinfo=timezone(timedelta(hours=-4)))
        # when: 서울 10-16 09:00의 업무 날짜를 구한다
        actual = business_date(evening)
        # then: 10-16이다
        assert actual == date(2026, 10, 16)

    def test_year_end_rolls_over(self, local_tz: Callable[[str], None]) -> None:
        """연말 UTC 15:00은 서울 새해 첫날이다.

        테스트 코드: TM-012
        """
        # given: 서버 시간대 Asia/Seoul
        local_tz("Asia/Seoul")
        # when: 2026-12-31T15:00Z의 업무 날짜를 구한다
        actual = business_date(datetime(2026, 12, 31, 15, 0, tzinfo=UTC))
        # then: 2027-01-01이다
        assert actual == date(2027, 1, 1)


class TestLocalTimeZoneIsUtc:
    def test_utc_afternoon_after_1500_is_still_the_same_day(
        self, local_tz: Callable[[str], None]
    ) -> None:
        """서버 시간대가 UTC면 UTC 15시 이후도 같은 날이다.

        테스트 코드: TM-011
        """
        # given: 서버 시간대 UTC
        local_tz("UTC")
        # when: UTC 10-15 15:30의 업무 날짜를 구한다
        actual = business_date(datetime(2026, 10, 15, 15, 30, tzinfo=UTC))
        # then: 10-15다
        assert actual == date(2026, 10, 15)

    def test_the_last_minute_of_the_utc_day_keeps_its_date(
        self, local_tz: Callable[[str], None]
    ) -> None:
        """UTC 23:59도 그 날짜다.

        테스트 코드: TM-011
        """
        # given: 서버 시간대 UTC
        local_tz("UTC")
        # when: UTC 10-15 23:59의 업무 날짜를 구한다
        actual = business_date(datetime(2026, 10, 15, 23, 59, tzinfo=UTC))
        # then: 10-15다
        assert actual == date(2026, 10, 15)

    def test_utc_midnight_starts_the_next_day(self, local_tz: Callable[[str], None]) -> None:
        """UTC 자정은 다음 날이 시작된다.

        테스트 코드: TM-011
        """
        # given: 서버 시간대 UTC
        local_tz("UTC")
        # when: UTC 10-16 00:00의 업무 날짜를 구한다
        actual = business_date(datetime(2026, 10, 16, 0, 0, tzinfo=UTC))
        # then: 10-16이다
        assert actual == date(2026, 10, 16)

    def test_a_seoul_offset_time_is_converted_to_utc_first(
        self, local_tz: Callable[[str], None]
    ) -> None:
        """서울 오프셋 시각도 UTC로 먼저 바꾼 뒤 날짜를 정한다.

        테스트 코드: TM-012
        """
        # given: 서버 시간대 UTC, +09:00 오프셋의 10-16 08:00
        local_tz("UTC")
        seoul_morning = datetime(2026, 10, 16, 8, 0, tzinfo=timezone(timedelta(hours=9)))
        # when: 10-15 23:00Z의 업무 날짜를 구한다
        actual = business_date(seoul_morning)
        # then: 10-15다
        assert actual == date(2026, 10, 15)


def test_a_zone_behind_utc_uses_its_own_calendar(local_tz: Callable[[str], None]) -> None:
    """UTC보다 늦은 시간대는 자기 달력을 쓴다(뉴욕은 UTC 02시가 전날).

    테스트 코드: TM-011
    """
    # given: 서버 시간대 America/New_York(10월은 UTC-4)
    local_tz("America/New_York")
    # when: 2026-10-16T02:00Z의 업무 날짜를 구한다
    actual = business_date(datetime(2026, 10, 16, 2, 0, tzinfo=UTC))
    # then: 10-15다
    assert actual == date(2026, 10, 15)
