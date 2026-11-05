"""저장 폴더 규칙의 한 곳: Deal 첨부는 `<deal_code>`, 계약 첨부는 `license-contracts/<계약 id>`."""

from typing import TYPE_CHECKING

from app.application.ports.file_storage import StorageFolder

if TYPE_CHECKING:
    from app.domain.deal.code import DealCode
    from app.domain.license_contract.values import LicenseContractId

LICENSE_CONTRACTS_DIR = "license-contracts"


def deal_folder(deal_code: DealCode) -> StorageFolder:
    return StorageFolder(parts=(deal_code.value,))


def license_contract_folder(contract_id: LicenseContractId) -> StorageFolder:
    return StorageFolder(parts=(LICENSE_CONTRACTS_DIR, str(int(contract_id))))
