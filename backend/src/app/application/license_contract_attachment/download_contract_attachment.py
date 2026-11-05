from typing import TYPE_CHECKING

from app.application.ports.file_storage import (
    StorageNotReadableError,
    StoredFileLocation,
    StoredFileMissingError,
)
from app.application.storage.errors import DOWNLOAD_UNAVAILABLE, StorageUnavailableError
from app.application.storage.folders import license_contract_folder
from app.domain.attachment.errors import AttachmentContentMissingError

if TYPE_CHECKING:
    from app.application.ports.file_storage import FileStorage, OpenedFile
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.license_contract.attachment import ContractAttachment
    from app.domain.license_contract.values import ContractAttachmentId


class DownloadContractAttachment:
    """계약 첨부 내용을 연다. 설정 없음·읽기 불가는 503, 내용 없음은 404."""

    def __init__(self, uow_factory: UnitOfWorkFactory, storage: FileStorage) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def execute(
        self, attachment_id: ContractAttachmentId
    ) -> tuple[ContractAttachment, OpenedFile]:
        async with self._uow_factory() as uow:
            attachment = await uow.license_contract_attachments.get(attachment_id)
            settings = await uow.storage_settings.get()
        if settings is None:
            raise StorageUnavailableError(DOWNLOAD_UNAVAILABLE)
        try:
            location = StoredFileLocation(
                folder=license_contract_folder(attachment.contract_id), key=attachment.storage_key
            )
            opened = await self._storage.open(settings.path, location)
        except StoredFileMissingError:
            raise AttachmentContentMissingError from None
        except StorageNotReadableError:
            raise StorageUnavailableError(DOWNLOAD_UNAVAILABLE) from None
        return attachment, opened
