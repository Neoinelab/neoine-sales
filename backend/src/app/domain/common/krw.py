"""원화 금액 표기(천원 단위)."""

HALF_THOUSAND = 500
THOUSAND = 1000


def to_thousand_won(amount: int) -> int:
    """원 → 천원(half-up 반올림, 프런트 `toThousandWon`과 같다). 금액은 0 이상이다."""
    return (amount + HALF_THOUSAND) // THOUSAND


def format_thousand_won(amount: int) -> str:
    """원 금액을 천원 단위 콤마 숫자로(단위 글자 없음). 예: 1,870,000,000 → '1,870,000'."""
    return f"{to_thousand_won(amount):,}"
