"""금액 천원 표기: 프런트 `formatThousandWon`·`toThousandWon`과 같은 half-up 규칙."""

import pytest

from app.domain.common.krw import format_thousand_won, to_thousand_won


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (1_870_000_000, "1,870,000"),
        (150_000_000, "150,000"),
        (1_000, "1"),
        (1_234_567, "1,235"),
        (1_234_499, "1,234"),
        (1_500, "2"),
        (2_500, "3"),
        (499, "0"),
        (500, "1"),
        (0, "0"),
        (2**53 - 1, "9,007,199,254,741"),
    ],
)
def test_format_thousand_won_rounds_half_up_with_commas(amount: int, expected: str) -> None:
    assert format_thousand_won(amount) == expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (1_499, 1),
        (1_500, 2),
        (2_500, 3),
        (999, 1),
        (0, 0),
        (2**53 - 1, 9_007_199_254_741),
    ],
)
def test_to_thousand_won_rounds_half_up(amount: int, expected: int) -> None:
    assert to_thousand_won(amount) == expected
