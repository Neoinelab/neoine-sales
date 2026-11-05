"""라이선스 계약의 값 객체: 상태, 점검주기, 기간, 계약 칸."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, NewType

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import assign, reject_nul
from app.domain.license_contract.term import TermUnit, license_end

if TYPE_CHECKING:
    from datetime import date

__all__ = [
    "NOTE_MAX",
    "TECH_OWNER_MAX",
    "TERM_MAX",
    "TERM_MIN",
    "ContractAttachmentId",
    "ContractFields",
    "ContractStatus",
    "InspectionCycle",
    "LicenseContractId",
    "LicenseTerm",
    "TermUnit",
]

LicenseContractId = NewType("LicenseContractId", int)
ContractAttachmentId = NewType("ContractAttachmentId", int)

TECH_OWNER_MAX = 100
NOTE_MAX = 2000
TERM_MIN = 1
TERM_MAX = 99


class ContractStatus(StrEnum):
    NOT_ISSUED = "not_issued"
    ISSUED_NEW = "issued_new"
    ISSUED_RENEWAL = "issued_renewal"
    ENDED = "ended"

    @property
    def is_issued(self) -> bool:
        return self in (ContractStatus.ISSUED_NEW, ContractStatus.ISSUED_RENEWAL)


class InspectionCycle(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    YEARLY = "yearly"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class LicenseTerm:
    """라이선스 기간(1~99 개월 또는 년)."""

    amount: int
    unit: TermUnit

    def __post_init__(self) -> None:
        if not TERM_MIN <= self.amount <= TERM_MAX:
            raise InvalidValueError(f"기간은 {TERM_MIN}~{TERM_MAX} 사이여야 합니다")

    def end_for(self, start: date) -> date:
        return license_end(start, self.amount, self.unit)


def _checked_text(value: str, field: str, max_length: int) -> str:
    reject_nul(value, field)
    text = value.strip()
    if len(text) > max_length:
        raise InvalidValueError(f"{field}은(는) {max_length}자를 넘을 수 없습니다")
    return text


@dataclass(frozen=True, slots=True)
class ContractFields:
    """계약 자체 칸: 기술담당(자유 텍스트), 점검주기, Note. 앞뒤 공백을 지우고 비어도 된다."""

    tech_owner: str
    inspection: InspectionCycle
    note: str

    def __post_init__(self) -> None:
        assign(
            self,
            tech_owner=_checked_text(self.tech_owner, "기술담당", TECH_OWNER_MAX),
            note=_checked_text(self.note, "Note", NOTE_MAX),
        )

    @classmethod
    def empty(cls) -> ContractFields:
        return cls(tech_owner="", inspection=InspectionCycle.NONE, note="")
