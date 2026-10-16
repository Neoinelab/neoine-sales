import logging
from typing import TYPE_CHECKING

from app.application.ports.file_storage import StorageNotWritableError, StoredFileLocation

if TYPE_CHECKING:
    from app.application.ports.file_storage import FileStorage
    from app.domain.attachment.entities import Attachment
    from app.domain.deal.code import DealCode
    from app.domain.storage.path import StoragePath

logger = logging.getLogger(__name__)


async def remove_file_quietly(
    storage: FileStorage, root: StoragePath, deal_code: DealCode, key: str
) -> None:
    """디스크 파일 하나를 지운다. DB가 정본이므로 실패는 경고 로그만 남기고 넘어간다."""
    try:
        await storage.delete(root, StoredFileLocation(deal_code=deal_code, key=key))
    except StorageNotWritableError:
        logger.warning("attachment file cleanup failed deal=%s key=%s", deal_code.value, key)


def location_of(attachment: Attachment) -> StoredFileLocation:
    return StoredFileLocation(deal_code=attachment.deal_code, key=attachment.storage_key)
