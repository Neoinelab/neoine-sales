"""금액 원 표기: 프런트 `formatWon`과 같은 콤마 숫자(반올림 없음)."""

import pytest

from app.domain.common import krw
from app.domain.common.krw import format_won


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (1_870_000_000, "1,870,000,000"),
        (150_000_000, "150,000,000"),
        (1_234_567, "1,234,567"),
        (1_234_499, "1,234,499"),
        (1_500, "1,500"),
        (300, "300"),
        (1, "1"),
        (0, "0"),
        (2**53 - 1, "9,007,199,254,740,991"),
    ],
)
def test_format_won_adds_commas_without_rounding(amount: int, expected: str) -> None:
    assert format_won(amount) == expected


def test_thousand_won_helpers_are_removed() -> None:
    assert not hasattr(krw, "format_thousand_won")
    assert not hasattr(krw, "to_thousand_won")
