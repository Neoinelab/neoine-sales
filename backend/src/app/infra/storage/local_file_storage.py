"""FileStorage Port의 로컬 디스크 구현. I/O는 스레드에서 한다.

배치는 Deal 첨부 `<root>/<deal_code>/<key>`, 라이선스 계약 첨부
`<root>/license-contracts/<id>/<key>`이며 폴더 조각은 application이 정한다.
폴더 경로의 어느 조각이든 심볼릭 링크면 따라가지 않는다(의도된 보안 강화): 다운로드는 404,
삭제는 대상을 보존하고 조용히 통과, 저장은 거절한다.
"""

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.application.ports.file_storage import (
    OpenedFile,
    StorageNotReadableError,
    StorageNotWritableError,
    StoredFileMissingError,
)
from app.domain.attachment.values import FILE_TOO_LARGE
from app.domain.common.errors import InvalidValueError
from app.infra.storage import _io

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.file_storage import (
        StorageFolder,
        StoredFileLocation,
        UploadSource,
    )
    from app.domain.storage.path import StoragePath

logger = logging.getLogger(__name__)


def _log_failure(action: str, error: OSError) -> None:
    """원인은 로그로만 남긴다(경로 대신 오류 번호와 종류만, 응답에는 싣지 않는다)."""
    logger.warning(
        "file storage %s failed: %s (errno=%s)", action, type(error).__name__, error.errno
    )


class LocalFileStorage:
    async def check_writable(self, root: StoragePath) -> None:
        try:
            await asyncio.to_thread(_io.probe_writable, Path(root.value))
        except OSError as error:
            _log_failure("check_writable", error)
            raise StorageNotWritableError from error

    async def save(
        self,
        root: StoragePath,
        location: StoredFileLocation,
        source: UploadSource,
        *,
        max_bytes: int,
    ) -> int:
        parts = location.folder.parts
        path = _io.file_path(root.value, parts, location.key)
        descriptor: int | None = None
        try:
            await asyncio.to_thread(_io.make_folders, root.value, parts)
            descriptor = await asyncio.to_thread(_io.create_exclusive, path)
        except OSError as error:  # 같은 키가 이미 있는 FileExistsError 포함
            _log_failure("save", error)
            raise StorageNotWritableError from error
        try:
            return await self._write(descriptor, source, max_bytes)
        except BaseException as error:
            _io.remove_quietly(
                path
            )  # 요청 취소 중에도 정리가 끊기지 않도록 스레드 없이 동기로 한다
            if isinstance(error, OSError):
                _log_failure("save", error)
                raise StorageNotWritableError from error
            raise
        finally:
            _io.close_quietly(descriptor)

    @staticmethod
    async def _write(descriptor: int, source: UploadSource, max_bytes: int) -> int:
        total = 0
        while chunk := await source.read(_io.CHUNK_SIZE):
            total += len(chunk)
            if total > max_bytes:
                raise InvalidValueError(FILE_TOO_LARGE)
            await asyncio.to_thread(_io.write_all, descriptor, chunk)
        return total

    async def open(self, root: StoragePath, location: StoredFileLocation) -> OpenedFile:
        """존재·읽기 가능 여부만 확인하고 닫는다. 실제 열기는 첫 청크를 읽을 때 한다."""
        parts = location.folder.parts
        path = _io.file_path(root.value, parts, location.key)
        try:
            await asyncio.to_thread(_io.reject_linked_folders, root.value, parts)
            size = await asyncio.to_thread(_io.stat_regular_file, path)
            if size is None:
                raise StoredFileMissingError
            await asyncio.to_thread(_io.check_readable, path)
        except FileNotFoundError, NotADirectoryError:
            raise StoredFileMissingError from None
        except OSError as error:
            _log_failure("open", error)
            raise StorageNotReadableError from error
        return OpenedFile(size=size, chunks=self._stream(path))

    @staticmethod
    async def _stream(path: Path) -> AsyncIterator[bytes]:
        try:
            descriptor = await asyncio.to_thread(_io.open_for_read, path)
        except FileNotFoundError, NotADirectoryError:  # 확인 뒤 지워졌다
            raise StoredFileMissingError from None
        except OSError as error:
            _log_failure("stream", error)
            raise StorageNotReadableError from error
        try:
            while chunk := await asyncio.to_thread(_io.read_chunk, descriptor):
                yield chunk
        finally:
            _io.close_quietly(descriptor)

    async def delete(self, root: StoragePath, location: StoredFileLocation) -> None:
        parts = location.folder.parts
        path = _io.file_path(root.value, parts, location.key)
        try:
            await asyncio.to_thread(_io.reject_linked_folders, root.value, parts)
            await asyncio.to_thread(_io.delete_file, path)
        except NotADirectoryError:  # 링크·파일이 길을 막으면 지울 것이 없다
            return
        except OSError as error:
            _log_failure("delete", error)
            raise StorageNotWritableError from error

    async def delete_folder(self, root: StoragePath, folder: StorageFolder) -> None:
        _io.validate_folder(folder.parts)
        try:
            await asyncio.to_thread(_io.delete_folder, root.value, folder.parts)
        except OSError as error:
            _log_failure("delete_folder", error)
            raise StorageNotWritableError from error
