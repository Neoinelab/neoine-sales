"""라이선스 기간 계산(AC4): 종료일 = 시작일 + 기간 - 1일. 프런트 테스트와 같은 사례."""

from datetime import date

import pytest
from app.domain.license_contract.term import license_end
from app.domain.license_contract.values import LicenseTerm, TermUnit

from app.domain.common.errors import InvalidValueError


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
    assert license_end(start, amount, unit) == expected


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
    assert license_end(start, amount, unit) == expected


@pytest.mark.parametrize("amount", [1, 99])
def test_license_term_accepts_the_boundary_amounts(amount: int) -> None:
    term = LicenseTerm(amount=amount, unit=TermUnit.MONTH)

    assert (term.amount, term.unit) == (amount, TermUnit.MONTH)


@pytest.mark.parametrize("amount", [0, 100, -1])
def test_license_term_out_of_range_rejected(amount: int) -> None:
    with pytest.raises(InvalidValueError):
        LicenseTerm(amount=amount, unit=TermUnit.YEAR)


def test_term_end_for_uses_the_same_calculation() -> None:
    term = LicenseTerm(amount=1, unit=TermUnit.YEAR)

    assert term.end_for(date(2026, 1, 1)) == date(2026, 12, 31)
