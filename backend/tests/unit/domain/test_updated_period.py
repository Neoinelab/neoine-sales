"""최종 업데이트 기간 프리셋: 서버 업무 날짜 기준 달력 계산. 끝은 항상 오늘(포함)이다."""

from datetime import date

import pytest

from app.domain.deal.updated_period import (
    UpcomingPeriodPreset,
    UpdatedPeriodPreset,
    months_after,
    months_before,
)


def test_presets_are_listed_in_api_order() -> None:
    """프리셋은 API 순서(2w, 1m, 2m, 3m, 6m)로 나열된다."""
    # when: 프리셋 값을 순서대로 모은다
    values = [p.value for p in UpdatedPeriodPreset]

    # then: API 순서와 같다
    assert values == ["2w", "1m", "2m", "3m", "6m"]


def test_two_weeks_starts_fourteen_days_before_today() -> None:
    """2주 프리셋은 오늘보다 14일 전부터 오늘까지다."""
    # given: 기준 오늘
    today = date(2026, 10, 21)

    # when: 2주 범위를 구한다
    result = UpdatedPeriodPreset.TWO_WEEKS.range_until(today)

    # then: 14일 전부터 오늘까지다
    assert result == (date(2026, 10, 7), today)


def test_two_weeks_cross_month_and_year() -> None:
    """2주 범위는 월·연도 경계를 넘을 수 있다."""
    # when: 1월 5일 기준 2주 범위를 구한다
    start, end = UpdatedPeriodPreset.TWO_WEEKS.range_until(date(2026, 1, 5))

    # then: 시작은 전년 12월 22일이다
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
    """개월 프리셋은 같은 일자의 n개월 전부터다."""
    # given: 기준 오늘
    today = date(2026, 10, 21)

    # when: 프리셋 범위를 구한다
    result = preset.range_until(today)

    # then: 같은 일자의 n개월 전부터 오늘까지다
    assert result == (start, today)


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
    """시작 달에 해당 일자가 없으면 그 달 말일로 맞춘다."""
    # when: 프리셋 범위를 구한다
    result = preset.range_until(today)

    # then: 시작은 그 달 말일이다
    assert result == (start, today)


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
    """개월 프리셋은 연도 경계를 넘을 수 있다."""
    # when: 프리셋 범위를 구한다
    result = preset.range_until(today)

    # then: 시작은 전년 날짜다
    assert result == (start, today)


@pytest.mark.parametrize(
    ("day", "months", "expected"),
    [
        (date(2026, 10, 21), 1, date(2026, 9, 21)),
        (date(2026, 10, 21), 2, date(2026, 8, 21)),
        (date(2026, 10, 21), 3, date(2026, 7, 21)),
        (date(2026, 10, 21), 6, date(2026, 4, 21)),
        (date(2026, 3, 31), 1, date(2026, 2, 28)),
        (date(2024, 3, 31), 1, date(2024, 2, 29)),
        (date(2026, 8, 31), 6, date(2026, 2, 28)),
        (date(2026, 5, 31), 3, date(2026, 2, 28)),
        (date(2026, 12, 31), 6, date(2026, 6, 30)),
        (date(2026, 10, 31), 1, date(2026, 9, 30)),
        (date(2026, 1, 15), 3, date(2025, 10, 15)),
    ],
)
def test_months_before_keeps_the_day_or_falls_back_to_month_end(
    day: date, months: int, expected: date
) -> None:
    """n개월 전은 같은 날이고 없는 날은 그 달 말일이다.

    테스트 코드: TM-014
    """
    # when: n개월 전 날짜를 구한다
    actual = months_before(day, months)

    # then: 같은 날이거나 그 달 말일인 예상 날짜(expected)다
    assert actual == expected


def test_months_before_zero_is_the_same_day() -> None:
    """0개월 전은 같은 날이다.

    테스트 코드: TM-016
    """
    # when: 0개월 전 날짜를 구한다
    actual = months_before(date(2026, 10, 21), 0)

    # then: 같은 날이다
    assert actual == date(2026, 10, 21)


def test_months_before_twelve_lands_on_the_same_day_a_year_earlier() -> None:
    """12개월 전은 1년 전 같은 날이고 윤일은 2월 28일이다.

    테스트 코드: TM-016
    """
    # when: 12개월 전 날짜를 구한다
    ordinary = months_before(date(2026, 10, 21), 12)
    leap_day = months_before(date(2024, 2, 29), 12)

    # then: 1년 전 같은 날이고 윤일은 2월 28일이다
    assert ordinary == date(2025, 10, 21)
    assert leap_day == date(2023, 2, 28)


def test_negative_months_are_a_programming_error() -> None:
    """음수 개월 전은 ValueError다.

    테스트 코드: TM-016
    """
    # when·then: -1개월 전을 구하면 ValueError가 난다
    with pytest.raises(ValueError, match="months"):
        months_before(date(2026, 10, 21), -1)


def test_upcoming_presets_are_listed_in_api_order() -> None:
    """다가오는 기간 프리셋은 API 순서(1m, 2m)로 나열된다."""
    # when: 프리셋 값을 순서대로 모은다
    values = [p.value for p in UpcomingPeriodPreset]

    # then: API 순서와 같다
    assert values == ["1m", "2m"]


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
    """다가오는 기간은 오늘부터 n개월 뒤까지다."""
    # given: 기준 오늘
    today = date(2026, 10, 22)

    # when: 범위를 구한다
    result = preset.range_from(today)

    # then: 오늘부터 n개월 뒤까지다
    assert result == (today, end)


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
    """끝 달에 해당 일자가 없으면 그 달 말일로 맞춘다."""
    # when: 범위를 구한다
    result = preset.range_from(today)

    # then: 끝은 그 달 말일이다
    assert result == (today, end)


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
    """다가오는 기간은 연도 경계를 넘을 수 있다."""
    # when: 범위를 구한다
    result = preset.range_from(today)

    # then: 끝은 다음 해 날짜다
    assert result == (today, end)


@pytest.mark.parametrize(
    ("day", "months", "expected"),
    [
        (date(2026, 10, 22), 1, date(2026, 11, 22)),
        (date(2026, 10, 22), 2, date(2026, 12, 22)),
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2024, 1, 31), 1, date(2024, 2, 29)),
        (date(2026, 12, 31), 2, date(2027, 2, 28)),
        (date(2026, 3, 31), 1, date(2026, 4, 30)),
        (date(2026, 7, 31), 2, date(2026, 9, 30)),
        (date(2026, 11, 15), 2, date(2027, 1, 15)),
        (date(2026, 12, 1), 1, date(2027, 1, 1)),
    ],
)
def test_months_after_keeps_the_day_or_falls_back_to_month_end(
    day: date, months: int, expected: date
) -> None:
    """n개월 뒤는 같은 날이고 없는 날은 그 달 말일이다.

    테스트 코드: TM-015
    """
    # when: n개월 뒤 날짜를 구한다
    actual = months_after(day, months)

    # then: 같은 날이거나 그 달 말일인 예상 날짜(expected)다
    assert actual == expected


def test_months_after_zero_is_the_same_day() -> None:
    """0개월 뒤는 같은 날이다.

    테스트 코드: TM-016
    """
    # when: 0개월 뒤 날짜를 구한다
    actual = months_after(date(2026, 10, 22), 0)

    # then: 같은 날이다
    assert actual == date(2026, 10, 22)


def test_months_after_twelve_lands_on_the_same_day_a_year_later() -> None:
    """12개월 뒤는 1년 뒤 같은 날이고 윤일은 2월 28일이다.

    테스트 코드: TM-016
    """
    # when: 12개월 뒤 날짜를 구한다
    ordinary = months_after(date(2026, 10, 22), 12)
    leap_day = months_after(date(2024, 2, 29), 12)

    # then: 1년 뒤 같은 날이고 윤일은 2월 28일이다
    assert ordinary == date(2027, 10, 22)
    assert leap_day == date(2025, 2, 28)


def test_negative_months_after_is_a_programming_error() -> None:
    """음수 개월 뒤는 ValueError다.

    테스트 코드: TM-016
    """
    # when·then: -1개월 뒤를 구하면 ValueError가 난다
    with pytest.raises(ValueError, match="months"):
        months_after(date(2026, 10, 22), -1)
