from typing import TYPE_CHECKING

from app.application.attachment.storage_cleanup import location_of
from app.application.ports.file_storage import StorageNotReadableError, StoredFileMissingError
from app.application.storage.errors import DOWNLOAD_UNAVAILABLE, StorageUnavailableError
from app.domain.attachment.errors import AttachmentContentMissingError

if TYPE_CHECKING:
    from app.application.ports.file_storage import FileStorage, OpenedFile
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.attachment.entities import Attachment
    from app.domain.attachment.values import AttachmentId


class DownloadAttachment:
    """첨부 내용을 연다. 현재 저장 위치에서 찾는다.

    설정 없음·읽기 불가는 StorageUnavailableError(503),
    내용 없음은 AttachmentContentMissingError(404).
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, storage: FileStorage) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def execute(self, attachment_id: AttachmentId) -> tuple[Attachment, OpenedFile]:
        async with self._uow_factory() as uow:
            attachment = await uow.attachments.get(attachment_id)
            settings = await uow.storage_settings.get()
        if settings is None:
            raise StorageUnavailableError(DOWNLOAD_UNAVAILABLE)
        try:
            opened = await self._storage.open(settings.path, location_of(attachment))
        except StoredFileMissingError:
            raise AttachmentContentMissingError from None
        except StorageNotReadableError:
            raise StorageUnavailableError(DOWNLOAD_UNAVAILABLE) from None
        return attachment, opened
