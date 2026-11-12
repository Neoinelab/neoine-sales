"""ListUpdatedPeriods: 서버 업무 날짜(OS 로컬)로 최종 업데이트 프리셋 범위를 풀어 준다."""

from datetime import date, datetime

from app.application.deal.updated_periods import ListUpdatedPeriods
from app.domain.deal.updated_period import UpcomingPeriodPreset, UpdatedPeriodPreset
from tests.fakes.unit_of_work import FixedClock


def _clock(day: date) -> FixedClock:
    return FixedClock(datetime(day.year, day.month, day.day, 12, 0).astimezone())


async def test_periods_are_resolved_from_the_server_business_date() -> None:
    """최종 업데이트 프리셋이 서버 업무 날짜 기준 범위로 풀리는지 확인한다."""
    # when: 2026-03-31 시계로 기간 목록을 조회한다
    view = await ListUpdatedPeriods(_clock(date(2026, 3, 31))).execute()

    # then: 오늘·종료일·프리셋별 시작일이 말일 맞춤으로 계산된다
    assert view.today == date(2026, 3, 31)
    assert [p.preset for p in view.periods] == list(UpdatedPeriodPreset)
    assert all(p.end == view.today for p in view.periods)
    by_preset = {p.preset: p.start for p in view.periods}
    assert by_preset[UpdatedPeriodPreset.TWO_WEEKS] == date(2026, 3, 17)
    assert by_preset[UpdatedPeriodPreset.ONE_MONTH] == date(2026, 2, 28)
    assert by_preset[UpdatedPeriodPreset.SIX_MONTHS] == date(2025, 9, 30)


async def test_the_business_date_follows_the_clock() -> None:
    """시계가 하루 지나면 업무 날짜와 기간이 따라 바뀌는지 확인한다."""
    clock = _clock(date(2026, 10, 21))
    use_case = ListUpdatedPeriods(clock)

    # when: 조회하고 시계를 하루 넘긴 뒤 다시 조회한다
    first = await use_case.execute()
    clock.advance(24 * 3600)
    second = await use_case.execute()

    # then: 오늘이 10-21에서 10-22로 바뀌고 첫 기간 시작일이 10-08이다
    assert (first.today, second.today) == (date(2026, 10, 21), date(2026, 10, 22))
    assert second.periods[0].start == date(2026, 10, 8)


async def test_the_ranges_match_the_domain_rule() -> None:
    """각 기간 범위가 도메인 규칙과 같은지 확인한다."""
    today = date(2026, 10, 21)

    # when: 기간 목록을 조회한다
    view = await ListUpdatedPeriods(_clock(today)).execute()

    # then: 모든 기간이 프리셋의 range_until 결과와 같다
    for period in view.periods:
        assert (period.start, period.end) == period.preset.range_until(today)


async def test_upcoming_periods_are_resolved_from_the_server_business_date() -> None:
    """예정 기간 프리셋이 서버 업무 날짜에서 시작하는 범위로 풀리는지 확인한다."""
    # when: 2026-01-31 시계로 기간 목록을 조회한다
    view = await ListUpdatedPeriods(_clock(date(2026, 1, 31))).execute()

    # then: 모든 시작일이 오늘이고 종료일이 말일 맞춤으로 계산된다
    assert [u.preset for u in view.upcoming] == list(UpcomingPeriodPreset)
    assert all(u.start == date(2026, 1, 31) for u in view.upcoming)
    by_preset = {u.preset: u.end for u in view.upcoming}
    assert by_preset[UpcomingPeriodPreset.ONE_MONTH] == date(2026, 2, 28)
    assert by_preset[UpcomingPeriodPreset.TWO_MONTHS] == date(2026, 3, 31)


async def test_upcoming_follows_the_clock() -> None:
    """시계가 하루 지나면 예정 기간 시작일이 따라 바뀌는지 확인한다."""
    clock = _clock(date(2026, 10, 21))
    use_case = ListUpdatedPeriods(clock)

    # when: 조회하고 시계를 하루 넘긴 뒤 다시 조회한다
    first = await use_case.execute()
    clock.advance(24 * 3600)
    second = await use_case.execute()

    # then: 첫 예정 기간 시작일이 10-21에서 10-22로 바뀐다
    assert (first.upcoming[0].start, second.upcoming[0].start) == (
        date(2026, 10, 21),
        date(2026, 10, 22),
    )


async def test_upcoming_ranges_match_the_domain_rule() -> None:
    """각 예정 기간 범위가 도메인 규칙과 같은지 확인한다."""
    today = date(2026, 10, 21)

    # when: 기간 목록을 조회한다
    view = await ListUpdatedPeriods(_clock(today)).execute()

    # then: 모든 예정 기간이 프리셋의 range_from 결과와 같다
    for item in view.upcoming:
        assert (item.start, item.end) == item.preset.range_from(today)
