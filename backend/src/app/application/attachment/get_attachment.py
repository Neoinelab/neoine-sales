from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.attachment.entities import Attachment
    from app.domain.attachment.values import AttachmentId


class GetAttachment:
    """첨부 한 건. 없으면 AttachmentNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, attachment_id: AttachmentId) -> Attachment:
        async with self._uow_factory() as uow:
            return await uow.attachments.get(attachment_id)
