"""YearMonth·기본 기준 월·허용 기준 월(P6 R2 AC-13·15, Q4=A·Q5=A).

기준 월은 `YYYY-MM` 한 형식뿐이다. 기본 대상은 실행일의 전월이고, 다시 계산할 수 있는 월은 전월과
당월뿐이다(그 이전은 현재 데이터가 그 시점을 나타내지 않아 거부, 미래도 거부).
"""

from datetime import date

import pytest
from app.domain.forecast.snapshot import YearMonth, default_snapshot_month, ensure_snapshot_allowed

from app.domain.common.errors import InvalidValueError
from app.domain.forecast.errors import SnapshotMonthNotAllowedError


def test_parse_reads_a_year_and_a_two_digit_month() -> None:
    assert YearMonth.parse("2026-09") == YearMonth(2026, 9)
    assert YearMonth.parse("2026-12") == YearMonth(2026, 12)


def test_text_form_is_zero_padded() -> None:
    assert str(YearMonth(2026, 9)) == "2026-09"
    assert str(YearMonth(2027, 1)) == "2027-01"
    assert str(YearMonth(2026, 12)) == "2026-12"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "2026-9",
        "2026-13",
        "2026-00",
        "202609",
        "2026/09",
        " 2026-09",
        "2026-09 ",
        "2026-09\n",
        "2026-09-01",
        "26-09",
        "abcd-ef",
        "\uff12\uff10\uff12\uff16-\uff10\uff19",  # 전각 숫자
    ],
)
def test_parse_rejects_anything_but_yyyy_mm(text: str) -> None:
    with pytest.raises(InvalidValueError):
        YearMonth.parse(text)


def test_previous_goes_back_one_month() -> None:
    assert YearMonth(2026, 10).previous() == YearMonth(2026, 9)


def test_previous_of_january_is_the_december_of_the_year_before() -> None:
    assert YearMonth(2026, 1).previous() == YearMonth(2025, 12)


def test_year_months_sort_by_year_then_month() -> None:
    months = [YearMonth(2027, 1), YearMonth(2026, 10), YearMonth(2026, 9)]

    assert sorted(months) == [YearMonth(2026, 9), YearMonth(2026, 10), YearMonth(2027, 1)]


def test_default_month_is_previous_month_on_first_day() -> None:
    assert default_snapshot_month(date(2026, 10, 1)) == YearMonth(2026, 9)


def test_january_run_targets_previous_december() -> None:
    assert default_snapshot_month(date(2026, 1, 1)) == YearMonth(2025, 12)


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 10, 17), YearMonth(2026, 9)),  # 한 달 중간에 늦게 보충 실행돼도 전월
        (date(2026, 3, 31), YearMonth(2026, 2)),
        (date(2026, 12, 31), YearMonth(2026, 11)),
    ],
)
def test_default_month_is_always_the_month_before_the_run_date(
    today: date, expected: YearMonth
) -> None:
    assert default_snapshot_month(today) == expected


@pytest.mark.parametrize("target", [YearMonth(2026, 9), YearMonth(2026, 10)])
def test_current_and_previous_month_are_allowed(target: YearMonth) -> None:
    ensure_snapshot_allowed(target, date(2026, 10, 15))  # 예외가 없으면 허용


def test_previous_month_across_the_new_year_is_allowed() -> None:
    ensure_snapshot_allowed(YearMonth(2025, 12), date(2026, 1, 10))


@pytest.mark.parametrize("target", [YearMonth(2026, 8), YearMonth(2026, 1), YearMonth(2025, 10)])
def test_older_month_raises_not_allowed(target: YearMonth) -> None:
    with pytest.raises(SnapshotMonthNotAllowedError) as caught:
        ensure_snapshot_allowed(target, date(2026, 10, 15))

    assert "다시 계산할 수 없습니다" in str(caught.value)


def test_two_months_back_across_the_new_year_raises_not_allowed() -> None:
    with pytest.raises(SnapshotMonthNotAllowedError):
        ensure_snapshot_allowed(YearMonth(2025, 11), date(2026, 1, 10))


@pytest.mark.parametrize("target", [YearMonth(2026, 11), YearMonth(2027, 1)])
def test_future_month_raises_not_allowed(target: YearMonth) -> None:
    with pytest.raises(SnapshotMonthNotAllowedError):
        ensure_snapshot_allowed(target, date(2026, 10, 15))


def test_not_allowed_is_an_invalid_value_error() -> None:
    assert issubclass(SnapshotMonthNotAllowedError, InvalidValueError)
