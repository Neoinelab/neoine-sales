"""Deal 값 객체: 금액, 견적, POC, BANT 선택, Deal 정보.

필드별 검증 함수(`check_*`)를 공개해 application 검증이 등록 폼의 순서대로 호출할 수 있게 한다.
문구는 프런트 목업 `validateDealFields`와 같다.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, TypeGuard

from app.domain.bant.values import BantCategory
from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import assign, reject_nul

if TYPE_CHECKING:
    from datetime import date

    from app.domain.bant.values import BantLabelId
    from app.domain.user.value_objects import UserId

NAME_MAX = 200
VENDOR_MAX = 100
SOLUTION_MAX = 200
PROCUREMENT_MAX = 500
AMOUNT_MAX = 2**53 - 1  # 프런트 Number.isSafeInteger와 같다
USERS_MAX = 2_147_483_647  # PostgreSQL integer 최대

AMOUNT_MESSAGE = "매출금액은 1원 이상의 정수로 입력하세요."
USERS_MESSAGE = "Users는 1 이상의 정수로 입력하세요."


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class RevenueAmount:
    """원화 정수 금액. 1 이상 AMOUNT_MAX 이하."""

    value: int

    def __post_init__(self) -> None:
        if not _is_int(self.value) or not 1 <= self.value <= AMOUNT_MAX:
            raise InvalidValueError(AMOUNT_MESSAGE)


class QuoteSubmitted(StrEnum):
    YES = "YES"
    NO = "NO"


class PocState(StrEnum):
    YES = "YES"
    ING = "ING"
    NO = "NO"


@dataclass(frozen=True, slots=True)
class Quote:
    """견적 제출 여부와 제출일. 둘의 조합은 검사하지 않는다."""

    submitted: QuoteSubmitted | None
    submitted_date: date | None


@dataclass(frozen=True, slots=True)
class Poc:
    """POC 상태와 완료일. 둘의 조합은 검사하지 않는다."""

    state: PocState | None
    completed_date: date | None


@dataclass(frozen=True, slots=True)
class BantSelection:
    """구분당 Label id 하나 또는 선택 안 함(None)."""

    budget: BantLabelId | None
    authority: BantLabelId | None
    need: BantLabelId | None
    timeline: BantLabelId | None

    def get(self, category: BantCategory) -> BantLabelId | None:
        return getattr(self, category.value)  # type: ignore[no-any-return]

    def with_(self, category: BantCategory, label_id: BantLabelId | None) -> BantSelection:
        values = {c.value: self.get(c) for c in BantCategory}
        values[category.value] = label_id
        return BantSelection(**values)


def check_name(raw: str) -> str:
    reject_nul(raw, "Deal Name")
    name = raw.strip()
    if not name:
        raise InvalidValueError("Deal Name을 입력하세요.")
    if len(name) > NAME_MAX:
        raise InvalidValueError(f"Deal Name은 {NAME_MAX}자 이내로 입력하세요.")
    return name


def _optional_limited(raw: str, label: str, limit: int, particle: str) -> str:
    reject_nul(raw, label)
    text = raw.strip()
    if len(text) > limit:
        raise InvalidValueError(f"{label}{particle} {limit}자 이내로 입력하세요.")
    return text


def check_vendor(raw: str) -> str:
    return _optional_limited(raw, "Vendor", VENDOR_MAX, "는")


def check_solution(raw: str) -> str:
    return _optional_limited(raw, "Solution", SOLUTION_MAX, "은")


def check_procurement(raw: str) -> str:
    return _optional_limited(raw, "구매절차", PROCUREMENT_MAX, "는")


def check_amount(value: object) -> RevenueAmount:
    """정수가 아니거나 범위 밖이면 InvalidValueError. int 외 값은 형 검사를 통과하지 못한다."""
    if not _is_int(value):
        raise InvalidValueError(AMOUNT_MESSAGE)
    return RevenueAmount(value)


def check_users(value: object) -> int | None:
    """None(선택)이거나 1..USERS_MAX 정수."""
    if value is None:
        return None
    if not _is_int(value) or not 1 <= value <= USERS_MAX:
        raise InvalidValueError(USERS_MESSAGE)
    return value


@dataclass(frozen=True, slots=True)
class DealDetails:
    """Deal의 정보 필드. code·Status/Forecast·고객·파트너·BANT는 Deal이 가진다."""

    name: str
    owner_user_id: UserId
    vendor: str
    solution: str
    users: int | None
    revenue_amount: RevenueAmount
    revenue_date: date
    quote: Quote
    poc: Poc
    procurement: str

    def __post_init__(self) -> None:
        assign(
            self,
            name=check_name(self.name),
            vendor=check_vendor(self.vendor),
            solution=check_solution(self.solution),
            users=check_users(self.users),
            procurement=check_procurement(self.procurement),
        )
