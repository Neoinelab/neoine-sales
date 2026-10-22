"""최종 업데이트 기간 프리셋(AC-9·10): 서버 업무 날짜 기준 달력 계산. 끝은 항상 오늘(포함)이다."""

from datetime import date

import pytest

from app.domain.deal.updated_period import (
    UpcomingPeriodPreset,
    UpdatedPeriodPreset,
    months_after,
    months_before,
)


def test_presets_are_listed_in_api_order() -> None:
    assert [p.value for p in UpdatedPeriodPreset] == ["2w", "1m", "2m", "3m", "6m"]


def test_two_weeks_starts_fourteen_days_before_today() -> None:
    today = date(2026, 10, 21)

    assert UpdatedPeriodPreset.TWO_WEEKS.range_until(today) == (date(2026, 10, 7), today)


def test_two_weeks_cross_month_and_year() -> None:
    start, end = UpdatedPeriodPreset.TWO_WEEKS.range_until(date(2026, 1, 5))

    assert (start, end) == (date(2025, 12, 22), date(2026, 1, 5))


@pytest.mark.parametrize(
    ("preset", "start"),
    [
        (UpdatedPeriodPreset.ONE_MONTH, date(2026, 9, 21)),
        (UpdatedPeriodPreset.TWO_MONTHS, date(2026, 8, 21)),
        (UpdatedPeriodPreset.THREE_MONTHS, date(2026, 7, 21)),
        (UpdatedPeriodPreset.SIX_MONTHS, date(2026, 4, 21)),
    ],
)
def test_months_keep_the_same_day_of_month(preset: UpdatedPeriodPreset, start: date) -> None:
    today = date(2026, 10, 21)

    assert preset.range_until(today) == (start, today)


@pytest.mark.parametrize(
    ("today", "preset", "start"),
    [
        (date(2026, 3, 31), UpdatedPeriodPreset.ONE_MONTH, date(2026, 2, 28)),
        (date(2024, 3, 31), UpdatedPeriodPreset.ONE_MONTH, date(2024, 2, 29)),
        (date(2026, 8, 31), UpdatedPeriodPreset.SIX_MONTHS, date(2026, 2, 28)),
        (date(2026, 5, 31), UpdatedPeriodPreset.THREE_MONTHS, date(2026, 2, 28)),
        (date(2026, 12, 31), UpdatedPeriodPreset.SIX_MONTHS, date(2026, 6, 30)),
        (date(2026, 10, 31), UpdatedPeriodPreset.ONE_MONTH, date(2026, 9, 30)),
    ],
)
def test_missing_day_falls_back_to_month_end(
    today: date, preset: UpdatedPeriodPreset, start: date
) -> None:
    assert preset.range_until(today) == (start, today)


@pytest.mark.parametrize(
    ("today", "preset", "start"),
    [
        (date(2026, 1, 15), UpdatedPeriodPreset.THREE_MONTHS, date(2025, 10, 15)),
        (date(2026, 2, 10), UpdatedPeriodPreset.SIX_MONTHS, date(2025, 8, 10)),
    ],
)
def test_months_cross_the_year_boundary(
    today: date, preset: UpdatedPeriodPreset, start: date
) -> None:
    assert preset.range_until(today) == (start, today)


def test_months_before_zero_is_the_same_day() -> None:
    assert months_before(date(2026, 10, 21), 0) == date(2026, 10, 21)


def test_months_before_twelve_lands_on_the_same_day_a_year_earlier() -> None:
    assert months_before(date(2026, 10, 21), 12) == date(2025, 10, 21)
    assert months_before(date(2024, 2, 29), 12) == date(2023, 2, 28)


def test_negative_months_are_a_programming_error() -> None:
    with pytest.raises(ValueError, match="months"):
        months_before(date(2026, 10, 21), -1)


def test_upcoming_presets_are_listed_in_api_order() -> None:
    assert [p.value for p in UpcomingPeriodPreset] == ["1m", "2m"]


@pytest.mark.parametrize(
    ("preset", "end"),
    [
        (UpcomingPeriodPreset.ONE_MONTH, date(2026, 11, 22)),
        (UpcomingPeriodPreset.TWO_MONTHS, date(2026, 12, 22)),
    ],
)
def test_upcoming_range_starts_today_and_ends_n_months_later(
    preset: UpcomingPeriodPreset, end: date
) -> None:
    today = date(2026, 10, 22)

    assert preset.range_from(today) == (today, end)


@pytest.mark.parametrize(
    ("today", "preset", "end"),
    [
        (date(2026, 1, 31), UpcomingPeriodPreset.ONE_MONTH, date(2026, 2, 28)),
        (date(2024, 1, 31), UpcomingPeriodPreset.ONE_MONTH, date(2024, 2, 29)),
        (date(2026, 12, 31), UpcomingPeriodPreset.TWO_MONTHS, date(2027, 2, 28)),
        (date(2026, 3, 31), UpcomingPeriodPreset.ONE_MONTH, date(2026, 4, 30)),
        (date(2026, 7, 31), UpcomingPeriodPreset.TWO_MONTHS, date(2026, 9, 30)),
    ],
)
def test_upcoming_missing_day_falls_back_to_month_end(
    today: date, preset: UpcomingPeriodPreset, end: date
) -> None:
    assert preset.range_from(today) == (today, end)


@pytest.mark.parametrize(
    ("today", "preset", "end"),
    [
        (date(2026, 11, 15), UpcomingPeriodPreset.TWO_MONTHS, date(2027, 1, 15)),
        (date(2026, 12, 1), UpcomingPeriodPreset.ONE_MONTH, date(2027, 1, 1)),
    ],
)
def test_upcoming_range_crosses_the_year_boundary(
    today: date, preset: UpcomingPeriodPreset, end: date
) -> None:
    assert preset.range_from(today) == (today, end)


def test_months_after_zero_is_the_same_day() -> None:
    assert months_after(date(2026, 10, 22), 0) == date(2026, 10, 22)


def test_months_after_twelve_lands_on_the_same_day_a_year_later() -> None:
    assert months_after(date(2026, 10, 22), 12) == date(2027, 10, 22)
    assert months_after(date(2024, 2, 29), 12) == date(2025, 2, 28)


def test_negative_months_after_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="months"):
        months_after(date(2026, 10, 22), -1)
