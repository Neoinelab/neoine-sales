from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.license_contract.attachment import ContractAttachment
    from app.domain.license_contract.values import LicenseContractId


class ListContractAttachments:
    """한 계약의 첨부를 최신순으로 돌려준다. 없는 계약은 LicenseContractNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, contract_id: LicenseContractId) -> Sequence[ContractAttachment]:
        async with self._uow_factory() as uow:
            await uow.license_contracts.get(contract_id)
            return await uow.license_contract_attachments.list_by_contract(contract_id)
