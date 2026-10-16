"""원화 금액 표기."""


def format_krw_full(amount: int) -> str:
    """콤마로 자리를 끊은 숫자 + '원'. 예: 1,870,000,000원 (프런트 `formatKrwFull`)."""
    return f"{amount:,}원"
