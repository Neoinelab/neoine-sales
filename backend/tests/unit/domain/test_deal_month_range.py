"""month_range(P6 R1 AC-12): 그 달 1일~말일, 양끝 포함. Deal 목록과 Forecast가 같은 경계를 쓴다."""

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
    assert month_range(year, month) == (date(year, month, 1), end)


@pytest.mark.parametrize("month", [0, 13])
def test_month_range_rejects_a_month_outside_one_to_twelve(month: int) -> None:
    with pytest.raises(InvalidValueError):
        month_range(2026, month)
