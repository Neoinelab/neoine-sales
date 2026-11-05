from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.license_contract.attachment import ContractAttachment
    from app.domain.license_contract.values import ContractAttachmentId


class GetContractAttachment:
    """계약 첨부 한 건. 없으면 ContractAttachmentNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, attachment_id: ContractAttachmentId) -> ContractAttachment:
        async with self._uow_factory() as uow:
            return await uow.license_contract_attachments.get(attachment_id)
