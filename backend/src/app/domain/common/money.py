"""금액 값 객체."""

import re
from dataclasses import dataclass
from decimal import Decimal

from app.domain.common.errors import InvalidValueError

MAX_DECIMAL_PLACES = 4
MAX_AMOUNT = Decimal(10) ** 16  # 저장소(Numeric(20, 4))의 정수부 16자리를 넘지 못한다
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class Money:
    """통화가 있는 0 이상의 금액. 저장 시 값이 변하지 않도록 소수 4자리·정수부 16자리로 제한한다."""

    amount: Decimal
    currency: str = "KRW"

    def __post_init__(self) -> None:
        if not self.amount.is_finite() or self.amount < 0:
            raise InvalidValueError("금액은 0 이상의 유한한 수여야 합니다")
        exponent = self.amount.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -MAX_DECIMAL_PLACES:
            raise InvalidValueError(f"금액은 소수점 아래 {MAX_DECIMAL_PLACES}자리까지만 허용합니다")
        if self.amount >= MAX_AMOUNT:
            raise InvalidValueError("허용 범위(정수부 16자리)보다 큰 금액입니다")
        if not _CURRENCY_PATTERN.match(self.currency):
            raise InvalidValueError(f"통화 코드는 대문자 3자여야 합니다: {self.currency!r}")
