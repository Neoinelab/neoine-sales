"""금액 전체 표기(R-3): 프런트 `formatKrwFull`과 같다(콤마 숫자 + '원')."""

import pytest

from app.domain.common.krw import format_krw_full


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (1_870_000_000, "1,870,000,000원"),
        (150_000_000, "150,000,000원"),
        (1_000, "1,000원"),
        (999, "999원"),
        (1, "1원"),
        (0, "0원"),
        (2**53 - 1, "9,007,199,254,740,991원"),
    ],
)
def test_format_krw_full_groups_thousands_and_appends_won(amount: int, expected: str) -> None:
    assert format_krw_full(amount) == expected
