import logging
from typing import TYPE_CHECKING

from app.application.ports.file_storage import StorageNotWritableError, StoredFileLocation
from app.application.storage.folders import deal_folder

if TYPE_CHECKING:
    from app.application.ports.file_storage import FileStorage, StorageFolder
    from app.domain.attachment.entities import Attachment
    from app.domain.storage.path import StoragePath

logger = logging.getLogger(__name__)


async def remove_file_quietly(
    storage: FileStorage, root: StoragePath, location: StoredFileLocation
) -> None:
    """디스크 파일 하나를 지운다. DB가 정본이므로 실패는 경고 로그만 남기고 넘어간다."""
    try:
        await storage.delete(root, location)
    except StorageNotWritableError:
        logger.warning(
            "attachment file cleanup failed folder=%s key=%s",
            "/".join(location.folder.parts),
            location.key,
        )


async def remove_folder_quietly(
    storage: FileStorage, root: StoragePath, folder: StorageFolder
) -> None:
    """폴더를 통째로 지운다. 실패는 경고 로그만 남긴다."""
    try:
        await storage.delete_folder(root, folder)
    except StorageNotWritableError:
        logger.warning("storage folder cleanup failed folder=%s", "/".join(folder.parts))


def location_of(attachment: Attachment) -> StoredFileLocation:
    return StoredFileLocation(folder=deal_folder(attachment.deal_code), key=attachment.storage_key)
