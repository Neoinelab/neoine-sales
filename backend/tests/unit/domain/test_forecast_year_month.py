"""YearMonth·기본 기준 월·허용 기준 월.

기준 월은 `YYYY-MM` 한 형식뿐이다. 기본 대상은 실행일의 전월이고, 다시 계산할 수 있는 월은 전월과
당월뿐이다(그 이전은 현재 데이터가 그 시점을 나타내지 않아 거부, 미래도 거부).
"""

from datetime import date

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.forecast.errors import SnapshotMonthNotAllowedError
from app.domain.forecast.snapshot import YearMonth, default_snapshot_month, ensure_snapshot_allowed


def test_parse_reads_a_year_and_a_two_digit_month() -> None:
    """YYYY-MM 텍스트를 연·월로 읽는다"""
    # when: "2026-09"와 "2026-12"를 읽는다
    september = YearMonth.parse("2026-09")
    december = YearMonth.parse("2026-12")

    # then: 각 연·월이다
    assert september == YearMonth(2026, 9)
    assert december == YearMonth(2026, 12)


def test_text_form_is_zero_padded() -> None:
    """텍스트 형식은 월을 두 자리로 채운다"""
    # when: 9월·1월·12월을 텍스트로 만든다
    september = str(YearMonth(2026, 9))
    january = str(YearMonth(2027, 1))
    december = str(YearMonth(2026, 12))

    # then: 9월은 "2026-09", 1월은 "2027-01", 12월은 "2026-12"다
    assert september == "2026-09"
    assert january == "2027-01"
    assert december == "2026-12"


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
    """YYYY-MM이 아닌 텍스트는 InvalidValueError다"""
    # when·then: 형식이 틀린 텍스트(공백·전각 숫자 포함)를 읽으면 InvalidValueError다
    with pytest.raises(InvalidValueError):
        YearMonth.parse(text)


def test_previous_goes_back_one_month() -> None:
    """previous는 한 달 앞이다"""
    # when: 2026-10의 전월을 구한다
    previous = YearMonth(2026, 10).previous()
    # then: 2026-09다
    assert previous == YearMonth(2026, 9)


def test_previous_of_january_is_the_december_of_the_year_before() -> None:
    """1월의 전월은 전년 12월이다"""
    # when: 2026-01의 전월을 구한다
    previous = YearMonth(2026, 1).previous()
    # then: 2025-12다
    assert previous == YearMonth(2025, 12)


def test_year_months_sort_by_year_then_month() -> None:
    """기준 월은 연도 먼저 월 순으로 정렬된다"""
    # given: 섞인 순서의 기준 월
    months = [YearMonth(2027, 1), YearMonth(2026, 10), YearMonth(2026, 9)]

    # when: 정렬한다
    ordered = sorted(months)
    # then: 연도, 월 순이다
    assert ordered == [YearMonth(2026, 9), YearMonth(2026, 10), YearMonth(2027, 1)]


def test_default_month_is_previous_month_on_first_day() -> None:
    """기본 기준 월은 1일 실행이면 전월이다"""
    # when: 2026-10-01의 기본 기준 월을 구한다
    month = default_snapshot_month(date(2026, 10, 1))
    # then: 2026-09다
    assert month == YearMonth(2026, 9)


def test_january_run_targets_previous_december() -> None:
    """1월 실행의 기본 기준 월은 전년 12월이다"""
    # when: 2026-01-01의 기본 기준 월을 구한다
    month = default_snapshot_month(date(2026, 1, 1))
    # then: 2025-12다
    assert month == YearMonth(2025, 12)


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
    """기본 기준 월은 실행일의 전월이다 (보충 실행·말일 포함)"""
    # when: 기본 기준 월을 구한다
    month = default_snapshot_month(today)
    # then: 실행일의 전월이다
    assert month == expected


@pytest.mark.parametrize("target", [YearMonth(2026, 9), YearMonth(2026, 10)])
def test_current_and_previous_month_are_allowed(target: YearMonth) -> None:
    """전월·당월은 허용한다"""
    # when: 2026-10-15에 전월·당월을 확인한다
    ensure_snapshot_allowed(target, date(2026, 10, 15))

    # then: 예외 없이 통과한다(허용)


def test_previous_month_across_the_new_year_is_allowed() -> None:
    """연초의 전년 12월은 허용한다"""
    # when: 2026-01-10에 2025-12를 확인한다
    ensure_snapshot_allowed(YearMonth(2025, 12), date(2026, 1, 10))

    # then: 예외 없이 통과한다(허용)


@pytest.mark.parametrize("target", [YearMonth(2026, 8), YearMonth(2026, 1), YearMonth(2025, 10)])
def test_older_month_raises_not_allowed(target: YearMonth) -> None:
    """전전월 이전은 허용하지 않는다"""
    # when: 전전월 이전 기준 월을 확인한다
    with pytest.raises(SnapshotMonthNotAllowedError) as caught:
        ensure_snapshot_allowed(target, date(2026, 10, 15))

    # then: "다시 계산할 수 없습니다" 오류다
    assert "다시 계산할 수 없습니다" in str(caught.value)


def test_two_months_back_across_the_new_year_raises_not_allowed() -> None:
    """연초에 전전월(전년 11월)은 허용하지 않는다"""
    # when·then: 2026-01-10에 2025-11을 확인하면 SnapshotMonthNotAllowedError다
    with pytest.raises(SnapshotMonthNotAllowedError):
        ensure_snapshot_allowed(YearMonth(2025, 11), date(2026, 1, 10))


@pytest.mark.parametrize("target", [YearMonth(2026, 11), YearMonth(2027, 1)])
def test_future_month_raises_not_allowed(target: YearMonth) -> None:
    """다음 달 이후는 허용하지 않는다"""
    # when·then: 2026-10-15에 미래 기준 월을 확인하면 SnapshotMonthNotAllowedError다
    with pytest.raises(SnapshotMonthNotAllowedError):
        ensure_snapshot_allowed(target, date(2026, 10, 15))


def test_not_allowed_is_an_invalid_value_error() -> None:
    """허용되지 않는 기준 월 오류는 InvalidValueError의 한 종류다"""
    # when: 오류 클래스의 계통을 확인한다
    is_subclass = issubclass(SnapshotMonthNotAllowedError, InvalidValueError)

    # then: InvalidValueError의 하위 클래스다
    assert is_subclass
