from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.license_contract_repository import LicenseContractRow


@dataclass(frozen=True, slots=True)
class LicenseContractPage:
    items: Sequence[LicenseContractRow]
    total: int
    offset: int
    limit: int
