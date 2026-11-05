from typing import TYPE_CHECKING

from app.application.license_contract.dto import LicenseContractPage

if TYPE_CHECKING:
    from app.application.ports.license_contract_repository import LicenseContractQuery
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class ListLicenseContracts:
    """조건에 맞는 계약 한 페이지와 전체 건수."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: LicenseContractQuery) -> LicenseContractPage:
        async with self._uow_factory() as uow:
            items = await uow.license_contracts.search(query)
            total = await uow.license_contracts.count(query)
        return LicenseContractPage(items=items, total=total, offset=query.offset, limit=query.limit)
