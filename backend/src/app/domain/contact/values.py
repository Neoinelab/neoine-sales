"""연락처 값 객체: 종류, 식별자, 상세 정보."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, NewType

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import assign, optional_text, reject_nul

if TYPE_CHECKING:
    from app.domain.common.contact import Email, PhoneNumber

ContactId = NewType("ContactId", int)

COMPANY_MAX = 200
NAME_MAX = 100
TITLE_MAX = 100
WHITESPACE_MESSAGE = "공백은 입력할 수 없습니다."


class ContactKind(StrEnum):
    """연락처 종류. 선언 순서(고객 먼저)가 목록 정렬 순서다."""

    CUSTOMER = "customer"
    PARTNER = "partner"


def has_whitespace(value: str) -> bool:
    return any(ch.isspace() for ch in value)


def _identity_text(value: str, label: str, *, empty_message: str, max_length: int) -> str:
    """회사명·담당자명: strip하지 않고 공백이 하나라도 있으면 거절한다."""
    reject_nul(value, label)
    if not value:
        raise InvalidValueError(empty_message)
    if has_whitespace(value):
        raise InvalidValueError(WHITESPACE_MESSAGE)
    if len(value) > max_length:
        raise InvalidValueError(f"{label}은(는) {max_length}자를 넘을 수 없습니다")
    return value


@dataclass(frozen=True, slots=True)
class ContactDetails:
    """연락처 정보. 회사명·담당자명만 필수이고 나머지는 알 때만 채운다."""

    company: str
    name: str
    title: str | None
    email: Email | None
    phone: PhoneNumber | None

    def __post_init__(self) -> None:
        assign(
            self,
            company=_identity_text(
                self.company, "회사명", empty_message="회사명을 입력하세요.", max_length=COMPANY_MAX
            ),
            name=_identity_text(
                self.name, "담당자명", empty_message="담당자명을 입력하세요.", max_length=NAME_MAX
            ),
            title=optional_text(self.title, "직급", max_length=TITLE_MAX),
        )

    def same_as(self, other: ContactDetails) -> bool:
        """모든 값이 같은가(연락처가 실제로 바뀌었는지 판정)."""
        return self == other
