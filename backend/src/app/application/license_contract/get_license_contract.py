from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.license_contract_repository import LicenseContractRow
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.license_contract.values import LicenseContractId


class GetLicenseContract:
    """계약 한 건과 Deal 값. 없으면 LicenseContractNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, contract_id: LicenseContractId) -> LicenseContractRow:
        async with self._uow_factory() as uow:
            return await uow.license_contracts.get_row(contract_id)
