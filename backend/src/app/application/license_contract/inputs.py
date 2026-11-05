from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

    from app.domain.license_contract.values import ContractFields, LicenseTerm


@dataclass(frozen=True, slots=True)
class LicenseIssueInput:
    """발급·갱신 입력: 계약 칸과 시작일·기간. 종료일은 서버가 계산한다."""

    fields: ContractFields
    start: date
    term: LicenseTerm
