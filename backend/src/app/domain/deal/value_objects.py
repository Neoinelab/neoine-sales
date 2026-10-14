import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, NewType
from uuid import UUID

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import assign, required_text

if TYPE_CHECKING:
    from datetime import date

    from app.domain.common.money import Money
    from app.domain.customer.value_objects import CustomerId
    from app.domain.partner.value_objects import PartnerId
    from app.domain.user.value_objects import UserId

DealId = NewType("DealId", UUID)

CODE_MAX = 50
NAME_MAX = 200
VENDOR_MAX = 100
SOLUTION_MAX = 200
_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]*$")


@dataclass(frozen=True, slots=True)
class DealCode:
    """Deal 업무 키. 대문자로 정규화하며 영문·숫자로 시작하고 . _ - 를 쓸 수 있다."""

    value: str

    def __post_init__(self) -> None:
        code = required_text(self.value, "Deal Code", max_length=CODE_MAX).upper()
        if not _CODE_PATTERN.match(code):
            raise InvalidValueError(
                "Deal Code는 영문·숫자로 시작하고 영문, 숫자, '.', '_', '-'만 쓸 수 있습니다: "
                f"{self.value!r}"
            )
        assign(self, value=code)


@dataclass(frozen=True, slots=True)
class DealDetails:
    """Deal 정보: 요청된 7개 업무 필드 + 고객(필수)·파트너(선택) 참조."""

    code: DealCode
    name: str
    owner_user_id: UserId
    vendor: str
    solution: str
    revenue: Money
    revenue_date: date
    customer_id: CustomerId
    partner_id: PartnerId | None = None

    def __post_init__(self) -> None:
        assign(
            self,
            name=required_text(self.name, "Deal Name", max_length=NAME_MAX),
            vendor=required_text(self.vendor, "Vendor", max_length=VENDOR_MAX),
            solution=required_text(self.solution, "Solution", max_length=SOLUTION_MAX),
        )
