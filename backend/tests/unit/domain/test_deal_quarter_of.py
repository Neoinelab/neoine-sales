"""quarter_of(day): 날짜가 속한 분기(1~4). 경계일은 분기 첫날·마지막 날이다."""

from datetime import date

import pytest

from app.domain.deal.period import quarter_of, quarter_range


@pytest.mark.parametrize(
    ("day", "quarter"),
    [
        (date(2026, 1, 1), 1),
        (date(2026, 3, 31), 1),
        (date(2026, 4, 1), 2),
        (date(2026, 6, 30), 2),
        (date(2026, 7, 1), 3),
        (date(2026, 9, 30), 3),
        (date(2026, 10, 1), 4),
        (date(2026, 12, 31), 4),
        (date(2027, 1, 1), 1),
    ],
)
def test_quarter_of_returns_quarter_for_boundary_days(day: date, quarter: int) -> None:
    """날짜가 속한 분기는 경계일(분기 첫날·마지막 날)에서도 맞다.

    테스트 코드: DSH-013
    """
    # when: 경계일의 분기를 구한다
    result = quarter_of(day)

    # then: 12-31은 Q4, 01-01은 Q1, 03-31은 Q1, 04-01은 Q2처럼 맞다
    assert result == quarter


def test_quarter_of_a_leap_day_is_the_first_quarter() -> None:
    """윤일(2-29)은 Q1이다.

    BDD 밖: 분기 계산의 윤년 경계를 확인한다.
    """
    # when: 윤일의 분기를 구한다
    result = quarter_of(date(2028, 2, 29))

    # then: Q1이다
    assert result == 1


@pytest.mark.parametrize("quarter", [1, 2, 3, 4])
def test_every_day_of_a_quarter_range_maps_back_to_that_quarter(quarter: int) -> None:
    """분기 범위의 첫날·마지막 날은 그 분기로 되돌아온다.

    테스트 코드: DSH-013
    """
    # given: 2026년 해당 분기의 첫날·마지막 날
    start, end = quarter_range(2026, quarter)

    # when·then: 두 날의 분기를 구하면 그 분기다
    assert quarter_of(start) == quarter
    assert quarter_of(end) == quarter
