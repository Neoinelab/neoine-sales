from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.domain.deal.code import DealCode
    from app.domain.storage.path import StoragePath


class StorageNotWritableError(Exception):
    """저장 위치를 만들거나 쓸 수 없다(권한·읽기 전용 FS·파일이 있는 경로·디스크 부족 등).

    원인은 로그로만 남기고 사용자에게 싣지 않는다.
    """


class StoredFileMissingError(Exception):
    """열려는 파일이 디스크에 없다(파일·Deal 디렉터리 없음, Deal 자리가 일반 파일)."""


class StorageNotReadableError(Exception):
    """파일은 있어야 하지만 읽을 수 없다(권한·링크 순환·IO 오류 등).
    다운로드는 404가 아니라 503이다.

    `StoredFileMissingError`와 서로 하위 클래스가 아니다. 원인은 로그로만 남긴다.
    """


class UploadSource(Protocol):
    async def read(self, size: int = -1) -> bytes: ...  # Starlette UploadFile이 구조적으로 만족


@dataclass(frozen=True, slots=True)
class StoredFileLocation:
    deal_code: DealCode
    key: str  # 영숫자만. 경로 구분자·`..`·NUL·빈 값은 구현이 ValueError로 거절한다


@dataclass(frozen=True, slots=True)
class OpenedFile:
    size: int
    chunks: AsyncIterator[bytes]


class FileStorage(Protocol):
    async def check_writable(self, root: StoragePath) -> None:
        """root가 없으면 상위까지 만들고 흔적 없이 쓰기를 확인한다.

        실패는 StorageNotWritableError.
        """
        ...

    async def save(
        self,
        root: StoragePath,
        location: StoredFileLocation,
        source: UploadSource,
        *,
        max_bytes: int,
    ) -> int:
        """`<root>/<deal_code>/<key>`에 새로 쓰고 쓴 바이트 수를 돌려준다.

        같은 키가 있거나 쓰기에 실패하면 StorageNotWritableError, max_bytes를 넘으면
        InvalidValueError(FILE_TOO_LARGE). 실패하면 쓰던 파일을 남기지 않는다.
        """
        ...

    async def open(self, root: StoragePath, location: StoredFileLocation) -> OpenedFile:
        """없으면 StoredFileMissingError, 있지만 읽을 수 없으면 StorageNotReadableError.

        돌려준 `chunks`를 한 번도 읽지 않고 버려도 열린 파일이 남지 않아야 한다.
        """
        ...

    async def delete(self, root: StoragePath, location: StoredFileLocation) -> None:
        """없으면 조용히 통과. 실패는 StorageNotWritableError."""
        ...

    async def delete_deal_files(self, root: StoragePath, deal_code: DealCode) -> None:
        """`<root>/<deal_code>`를 통째로 지운다. 없으면 통과. 실패는 StorageNotWritableError."""
        ...
