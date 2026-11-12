"""라이선스 기간 계산(AC4): 종료일 = 시작일 + 기간 - 1일. 프런트 테스트와 같은 사례."""

from datetime import date

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.license_contract.term import license_end
from app.domain.license_contract.values import LicenseTerm, TermUnit


@pytest.mark.parametrize(
    ("start", "amount", "unit", "expected"),
    [
        (date(2026, 1, 1), 1, TermUnit.YEAR, date(2026, 12, 31)),
        (date(2026, 1, 1), 6, TermUnit.MONTH, date(2026, 6, 30)),
        (date(2026, 1, 1), 12, TermUnit.MONTH, date(2026, 12, 31)),
        (date(2026, 1, 1), 2, TermUnit.YEAR, date(2027, 12, 31)),
        (date(2026, 3, 15), 1, TermUnit.MONTH, date(2026, 4, 14)),
        (date(2026, 7, 1), 1, TermUnit.MONTH, date(2026, 7, 31)),
        (date(2026, 12, 1), 1, TermUnit.MONTH, date(2026, 12, 31)),
        (date(2026, 11, 15), 3, TermUnit.MONTH, date(2027, 2, 14)),
        (date(2026, 1, 31), 1, TermUnit.MONTH, date(2026, 2, 28)),
    ],
)
def test_license_end_matches_frontend_cases(
    start: date, amount: int, unit: TermUnit, expected: date
) -> None:
    """종료일은 시작일+기간-1일이고 프런트 계산과 같다.

    테스트 코드: LC-040
    """
    # when: 시작일과 기간으로 종료일을 계산한다
    actual = license_end(start, amount, unit)
    # then: 기대 종료일과 같다
    assert actual == expected


@pytest.mark.parametrize(
    ("start", "amount", "unit", "expected"),
    [
        (
            date(2028, 2, 29),
            1,
            TermUnit.YEAR,
            date(2029, 2, 28),
        ),  # 윤일 시작, 다음 해에 29일이 없다
        (date(2026, 3, 31), 1, TermUnit.MONTH, date(2026, 4, 30)),  # 시작일 - 1일이 말일 안
        (date(2026, 1, 1), 99, TermUnit.YEAR, date(2124, 12, 31)),  # 상한 기간
    ],
)
def test_license_end_handles_month_end_and_leap_boundaries(
    start: date, amount: int, unit: TermUnit, expected: date
) -> None:
    """윤일·말일·99년 같은 경계에서도 종료일이 맞다.

    테스트 코드: LC-040
    """
    # when: 경계 시작일로 종료일을 계산한다
    actual = license_end(start, amount, unit)
    # then: 기대 종료일과 같다
    assert actual == expected


@pytest.mark.parametrize("amount", [1, 99])
def test_license_term_accepts_the_boundary_amounts(amount: int) -> None:
    """기간 수량 1과 99는 허용된다.

    테스트 코드: LC-044
    """
    # when: 경계 수량으로 LicenseTerm을 만든다
    term = LicenseTerm(amount=amount, unit=TermUnit.MONTH)

    # then: 수량과 단위가 그대로다
    assert (term.amount, term.unit) == (amount, TermUnit.MONTH)


@pytest.mark.parametrize("amount", [0, 100, -1])
def test_license_term_out_of_range_rejected(amount: int) -> None:
    """기간 수량이 1~99 밖이면 거절된다.

    테스트 코드: LC-044
    """
    # when: 0·100·-1로 만든다
    with pytest.raises(InvalidValueError):
        LicenseTerm(amount=amount, unit=TermUnit.YEAR)
    # then: InvalidValueError


def test_term_end_for_uses_the_same_calculation() -> None:
    """LicenseTerm.end_for는 같은 계산을 쓴다.

    테스트 코드: LC-040
    """
    # given: 1년 기간
    term = LicenseTerm(amount=1, unit=TermUnit.YEAR)

    # when: 2026-01-01의 종료일을 구한다
    actual = term.end_for(date(2026, 1, 1))
    # then: 2026-12-31이다
    assert actual == date(2026, 12, 31)
