"""GetServerTime: 서버 시각과 업무 날짜를 Clock에서 한 번 읽어 계산한다(서버 시간 통일 AC1)."""

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from app.application.time.get_server_time import GetServerTime

from tests.fakes.unit_of_work import FixedClock, SteppingClock

if TYPE_CHECKING:
    from collections.abc import Callable

MOMENT = datetime(2026, 12, 31, 15, 30, tzinfo=UTC)


async def test_returns_local_now_and_business_date(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")

    view = await GetServerTime(FixedClock(MOMENT)).execute()

    assert view.now.isoformat() == "2027-01-01T00:30:00+09:00"
    assert view.now == MOMENT  # 순간은 Clock과 같다
    assert view.today == date(2027, 1, 1)


async def test_today_follows_utc_process_timezone(local_tz: Callable[[str], None]) -> None:
    local_tz("UTC")

    view = await GetServerTime(FixedClock(MOMENT)).execute()

    assert view.now.utcoffset() == timedelta(0)
    assert view.today == date(2026, 12, 31)


async def test_today_is_the_date_part_of_now(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")

    view = await GetServerTime(FixedClock(datetime(2026, 10, 22, 14, 59, tzinfo=UTC))).execute()

    assert view.today == view.now.date() == date(2026, 10, 22)


async def test_reads_the_clock_once_so_now_and_today_agree(
    local_tz: Callable[[str], None],
) -> None:
    local_tz("Asia/Seoul")
    # 두 번 읽으면 1초 뒤 값(자정 넘김)이 today에 섞인다: 23:59:59.x가 아니라 정각 직전으로 검증
    clock = SteppingClock(datetime(2026, 10, 22, 14, 59, 59, tzinfo=UTC))  # 로컬 23:59:59

    view = await GetServerTime(clock).execute()

    assert view.now.isoformat() == "2026-10-22T23:59:59+09:00"
    assert view.today == date(2026, 10, 22)
