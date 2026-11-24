from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.license_contract.values import resolve_license_end

if TYPE_CHECKING:
    from datetime import date

    from app.domain.license_contract.values import ContractFields, LicenseTerm


@dataclass(frozen=True, slots=True)
class LicenseIssueInput:
    fields: ContractFields
    start: date
    end: date | None = None
    term: LicenseTerm | None = None

    def __post_init__(self) -> None:
        resolve_license_end(self.start, self.end, self.term)
