"""check_meeting_date(AC17, P9): 필수 날짜, 1900-01-01~2999-12-31, 미래 날짜 허용, 시각 값 거절."""

from datetime import UTC, date, datetime

import pytest
from app.domain.partner_meeting.values import check_meeting_date

from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with

OUT_OF_BOUNDS = "미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"


@pytest.mark.parametrize("day", [date(1900, 1, 1), date(2026, 10, 28), date(2999, 12, 31)])
def test_dates_inside_the_bounds_are_returned_as_is(day: date) -> None:
    assert check_meeting_date(day) == day


@pytest.mark.parametrize("day", [date(1899, 12, 31), date(3000, 1, 1), date(1, 1, 1)])
def test_dates_outside_the_bounds_are_rejected_with_the_range_message(day: date) -> None:
    with raises_with(InvalidValueError, OUT_OF_BOUNDS):
        check_meeting_date(day)


def test_a_far_future_date_inside_the_bounds_is_allowed() -> None:
    assert check_meeting_date(date(2999, 1, 1)) == date(2999, 1, 1)


def test_a_datetime_is_rejected() -> None:
    with raises_with(InvalidValueError, "미팅 날짜는 시각 없는 날짜여야 합니다"):
        check_meeting_date(datetime(2026, 10, 1, 9, 0, tzinfo=UTC))
