from typing import TYPE_CHECKING

from app.application.ports.file_storage import StorageNotWritableError
from app.domain.common.errors import InvalidValueError
from app.domain.storage.path import PATH_NOT_WRITABLE

if TYPE_CHECKING:
    from app.application.ports.file_storage import FileStorage
    from app.domain.storage.path import StoragePath


async def ensure_writable(storage: FileStorage, path: StoragePath) -> None:
    """쓰기 확인 실패를 고정 문구의 InvalidValueError로 바꾼다. 원인(OS 오류·경로)은 담지 않는다."""
    try:
        await storage.check_writable(path)
    except StorageNotWritableError:
        raise InvalidValueError(PATH_NOT_WRITABLE) from None
