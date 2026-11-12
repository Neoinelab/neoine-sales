"""GetServerTime: 서버 시각과 업무 날짜를 Clock에서 한 번 읽어 계산한다."""

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from app.application.time.get_server_time import GetServerTime
from tests.fakes.unit_of_work import FixedClock, SteppingClock

if TYPE_CHECKING:
    from collections.abc import Callable

MOMENT = datetime(2026, 12, 31, 15, 30, tzinfo=UTC)


async def test_returns_local_now_and_business_date(local_tz: Callable[[str], None]) -> None:
    """서버 시각은 시계와 같은 순간의 서울 시각이고 오늘은 업무 날짜다.

    테스트 코드: TM-001
    """
    # given: 서버 시간대 Asia/Seoul, 서버 시계 2026-12-31T15:30Z
    local_tz("Asia/Seoul")
    # when: 서버 시각을 조회한다
    view = await GetServerTime(FixedClock(MOMENT)).execute()

    # then: now는 2027-01-01T00:30+09:00(순간은 시계와 같음), today는 2027-01-01
    assert view.now.isoformat() == "2027-01-01T00:30:00+09:00"
    assert view.now == MOMENT
    assert view.today == date(2027, 1, 1)


async def test_today_follows_utc_process_timezone(local_tz: Callable[[str], None]) -> None:
    """서버 시간대가 UTC면 오늘은 UTC 날짜이고 오프셋은 0이다.

    테스트 코드: TM-005
    """
    # given: 서버 시간대 UTC, 서버 시계 2026-12-31T15:30Z
    local_tz("UTC")
    # when: 서버 시각을 조회한다
    view = await GetServerTime(FixedClock(MOMENT)).execute()

    # then: 오프셋 0, today는 2026-12-31
    assert view.now.utcoffset() == timedelta(0)
    assert view.today == date(2026, 12, 31)


async def test_today_is_the_date_part_of_now(local_tz: Callable[[str], None]) -> None:
    """오늘은 항상 now의 날짜 부분이다.

    테스트 코드: TM-006
    """
    # given: 서버 시간대 Asia/Seoul, 서버 시계 2026-10-22T14:59Z(로컬 23:59)
    local_tz("Asia/Seoul")
    # when: 서버 시각을 조회한다
    view = await GetServerTime(FixedClock(datetime(2026, 10, 22, 14, 59, tzinfo=UTC))).execute()

    # then: today == now의 날짜 == 2026-10-22
    assert view.today == view.now.date() == date(2026, 10, 22)


async def test_reads_the_clock_once_so_now_and_today_agree(
    local_tz: Callable[[str], None],
) -> None:
    """서버 시계를 한 번만 읽어 자정 직전에도 now와 today가 같은 날이다.

    테스트 코드: TM-006
    """
    # given: 부를 때마다 1초 흐르는 시계가 로컬 23:59:59를 가리킨다(두 번 읽으면 다음 날이 섞인다)
    local_tz("Asia/Seoul")
    clock = SteppingClock(datetime(2026, 10, 22, 14, 59, 59, tzinfo=UTC))
    # when: 서버 시각을 조회한다
    view = await GetServerTime(clock).execute()

    # then: now는 23:59:59, today는 같은 날 2026-10-22
    assert view.now.isoformat() == "2026-10-22T23:59:59+09:00"
    assert view.today == date(2026, 10, 22)
