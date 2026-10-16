"""FileStorage Port의 InMemory 구현(Fake)과 업로드 원본 대역.

실제 구현(LocalFileStorage)과 같은 계약을 지킨다(`tests/unit/repositories/test_file_storage_*`):
- check_writable: 디렉터리를 (상위 포함) 만들고 흔적을 남기지 않는다. 쓸 수 없으면
  StorageNotWritableError.
- save: `<root>/<deal_code>/<key>`에 새로 쓰고 쓴 바이트 수를 돌려준다. 같은 키는 거절, 한도 초과는
  파일을 남기지 않고 InvalidValueError.
- open: 없으면 StoredFileMissingError, 있지만 읽을 수 없으면(`fail_reads`) StorageNotReadableError
  (두 오류는 서로 다른 종류다). delete·delete_deal_files: 없으면 조용히 통과.
- key가 영숫자가 아니면 ValueError(경로 조작 방어).

경로는 문자열 `<root>/<deal_code>/<key>`로 보관한다. 쓸 수 없는 root는 `block`으로 지정한다
(그 아래 경로도 쓸 수 없다). Port 모듈은 사용 시점에 가져온다(구현 전에도 수집된다).
"""

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.file_storage import OpenedFile, StoredFileLocation, UploadSource
    from app.domain.deal.code import DealCode
    from app.domain.storage.path import StoragePath

FILE_TOO_LARGE = "파일 크기가 100MB를 초과합니다. (최대 100MB)"
_CHUNK = 64 * 1024


class BytesSource:
    """UploadSource 대역: 메모리의 바이트를 청크로 읽어 준다(UploadFile처럼 read(size))."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0

    async def read(self, size: int = -1) -> bytes:
        end = len(self._data) if size < 0 else self._offset + size
        chunk = self._data[self._offset : end]
        self._offset += len(chunk)
        return chunk


def _valid_key(key: str) -> bool:
    return key.isascii() and key.isalnum()


class FakeFileStorage:
    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}
        self._dirs: set[str] = set()
        self._blocked: set[str] = set()
        self.checked: list[str] = []  # check_writable에 넘어온 root(성공·실패 모두)
        self.fail_deletes = False  # True면 delete·delete_deal_files가 StorageNotWritableError
        self.fail_reads = False  # True면 open이 (파일이 있어도) StorageNotReadableError

    # ---- 테스트 도우미 (Port가 아니다) ----

    def block(self, root: str) -> None:
        """root와 그 아래 경로를 쓸 수 없게 한다."""
        self._blocked.add(root)

    def dir_exists(self, path: str) -> bool:
        return path in self._dirs

    def entries(self, path: str) -> list[str]:
        """path 바로 아래의 이름(파일·디렉터리)을 정렬해 돌려준다."""
        parent = PurePosixPath(path)
        children = {
            PurePosixPath(p).name
            for p in (*self._dirs, *self._files)
            if PurePosixPath(p).parent == parent
        }
        return sorted(children - {""})

    def contents_of(self, root: StoragePath, location: StoredFileLocation) -> bytes | None:
        return self._files.get(self._file_path(root, location.deal_code, location.key))

    def file_count(self) -> int:
        return len(self._files)

    # ---- Port ----

    async def check_writable(self, root: StoragePath) -> None:
        from app.application.ports.file_storage import StorageNotWritableError  # noqa: PLC0415

        self.checked.append(root.value)
        if self._is_blocked(root.value):
            raise StorageNotWritableError
        self._make_dirs(root.value)

    async def save(
        self,
        root: StoragePath,
        location: StoredFileLocation,
        source: UploadSource,
        *,
        max_bytes: int,
    ) -> int:
        from app.application.ports.file_storage import StorageNotWritableError  # noqa: PLC0415
        from app.domain.common.errors import InvalidValueError  # noqa: PLC0415

        path = self._file_path(root, location.deal_code, location.key)
        if self._is_blocked(root.value) or path in self._files:
            raise StorageNotWritableError
        received = bytearray()
        while chunk := await source.read(_CHUNK):
            received.extend(chunk)
            if len(received) > max_bytes:
                raise InvalidValueError(FILE_TOO_LARGE)
        self._make_dirs(str(PurePosixPath(path).parent))
        self._files[path] = bytes(received)
        return len(received)

    async def open(self, root: StoragePath, location: StoredFileLocation) -> OpenedFile:
        from app.application.ports.file_storage import (  # noqa: PLC0415
            OpenedFile,
            StoredFileMissingError,
        )

        data = self._files.get(self._file_path(root, location.deal_code, location.key))
        if data is None:
            raise StoredFileMissingError
        if self.fail_reads:
            from app.application.ports.file_storage import (  # noqa: PLC0415 - 구현 전에도 수집
                StorageNotReadableError,
            )

            raise StorageNotReadableError

        async def chunks() -> AsyncIterator[bytes]:
            for start in range(0, len(data), _CHUNK):
                yield data[start : start + _CHUNK]

        return OpenedFile(size=len(data), chunks=chunks())

    async def delete(self, root: StoragePath, location: StoredFileLocation) -> None:
        from app.application.ports.file_storage import StorageNotWritableError  # noqa: PLC0415

        path = self._file_path(root, location.deal_code, location.key)
        if self.fail_deletes:
            raise StorageNotWritableError
        self._files.pop(path, None)

    async def delete_deal_files(self, root: StoragePath, deal_code: DealCode) -> None:
        from app.application.ports.file_storage import StorageNotWritableError  # noqa: PLC0415

        if self.fail_deletes:
            raise StorageNotWritableError
        directory = f"{root.value.rstrip('/')}/{deal_code.value}"
        self._files = {p: d for p, d in self._files.items() if not p.startswith(directory + "/")}
        self._dirs = {d for d in self._dirs if d != directory and not d.startswith(directory + "/")}

    # ---- 내부 ----

    def _is_blocked(self, root: str) -> bool:
        return any(root == b or root.startswith(b.rstrip("/") + "/") for b in self._blocked)

    def _make_dirs(self, path: str) -> None:
        current = PurePosixPath(path)
        self._dirs.update(str(p) for p in (current, *current.parents))

    @staticmethod
    def _file_path(root: StoragePath, deal_code: DealCode, key: str) -> str:
        if not _valid_key(key):
            raise ValueError(key)
        return f"{root.value.rstrip('/')}/{deal_code.value}/{key}"
