"""month_range: 그 달 1일~말일, 양끝 포함. Deal 목록과 Forecast가 같은 경계를 쓴다."""

from datetime import date

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal.period import month_range


@pytest.mark.parametrize(
    ("year", "month", "end"),
    [
        (2026, 1, date(2026, 1, 31)),
        (2026, 2, date(2026, 2, 28)),
        (2028, 2, date(2028, 2, 29)),
        (2026, 9, date(2026, 9, 30)),
        (2026, 12, date(2026, 12, 31)),
    ],
)
def test_month_range_spans_first_to_last_day(year: int, month: int, end: date) -> None:
    """달의 1일부터 말일까지를 돌려준다(윤년 2월 포함)."""
    # when: 연월로 범위를 구한다
    window = month_range(year, month)
    # then: 1일과 말일이다
    assert window == (date(year, month, 1), end)


@pytest.mark.parametrize("month", [0, 13])
def test_month_range_rejects_a_month_outside_one_to_twelve(month: int) -> None:
    """1~12 밖의 월은 거부한다."""
    # when·then: 범위 밖 월로 구하면 값 오류다
    with pytest.raises(InvalidValueError):
        month_range(2026, month)
