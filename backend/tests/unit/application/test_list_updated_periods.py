"""ListUpdatedPeriods(AC-9·10): 서버 업무 날짜(OS 로컬)로 최종 업데이트 프리셋 범위를 풀어 준다."""

from datetime import date, datetime

from app.application.deal.updated_periods import ListUpdatedPeriods
from app.domain.deal.updated_period import UpdatedPeriodPreset

from tests.fakes.unit_of_work import FixedClock


def _clock(day: date) -> FixedClock:
    return FixedClock(datetime(day.year, day.month, day.day, 12, 0).astimezone())


async def test_periods_are_resolved_from_the_server_business_date() -> None:
    view = await ListUpdatedPeriods(_clock(date(2026, 3, 31))).execute()

    assert view.today == date(2026, 3, 31)
    assert [p.preset for p in view.periods] == list(UpdatedPeriodPreset)
    assert all(p.end == view.today for p in view.periods)
    by_preset = {p.preset: p.start for p in view.periods}
    assert by_preset[UpdatedPeriodPreset.TWO_WEEKS] == date(2026, 3, 17)
    assert by_preset[UpdatedPeriodPreset.ONE_MONTH] == date(2026, 2, 28)
    assert by_preset[UpdatedPeriodPreset.SIX_MONTHS] == date(2025, 9, 30)


async def test_the_business_date_follows_the_clock() -> None:
    clock = _clock(date(2026, 10, 21))
    use_case = ListUpdatedPeriods(clock)

    first = await use_case.execute()
    clock.advance(24 * 3600)
    second = await use_case.execute()

    assert (first.today, second.today) == (date(2026, 10, 21), date(2026, 10, 22))
    assert second.periods[0].start == date(2026, 10, 8)


async def test_the_ranges_match_the_domain_rule() -> None:
    today = date(2026, 10, 21)

    view = await ListUpdatedPeriods(_clock(today)).execute()

    for period in view.periods:
        assert (period.start, period.end) == period.preset.range_until(today)
