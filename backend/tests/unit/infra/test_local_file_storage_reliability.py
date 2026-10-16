"""LocalFileStorage의 자원·실패 처리(P2b R1 리뷰 Minor 1~3): fd 누수, 읽기 불가, 저장 실패 정리.

모두 tmp_path 아래 실제 디렉터리에서 돈다. 열린 파일 수는 `/dev/fd`로 센다(리눅스·macOS 공통).
읽기 권한 오류는 root 사용자로 돌려도 같은 결과가 나도록 권한 비트 대신 "자기 자신을 가리키는 심볼릭
링크"(ELOOP, 파일 없음이 아닌 읽기 실패)로 만든다.
"""

import errno
import gc
import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.ports.file_storage import (
    StorageNotReadableError,
    StorageNotWritableError,
    StoredFileLocation,
    StoredFileMissingError,
)
from app.domain.deal.code import DealCode
from app.domain.storage.path import StoragePath
from app.infra.storage import _io
from app.infra.storage.local_file_storage import LocalFileStorage
from tests.fakes.file_storage import BytesSource
from tests.fakes.sources import ClientGone, FailingSource

DEAL = DealCode("20261016-A001")


def _open_descriptors() -> int:
    gc.collect()
    return len(os.listdir("/dev/fd"))


@pytest.fixture
def root(tmp_path: Path) -> StoragePath:
    return StoragePath.parse(str(tmp_path / "files"))


def _location() -> StoredFileLocation:
    return StoredFileLocation(deal_code=DEAL, key=uuid4().hex)


def _deal_dir(root: StoragePath) -> Path:
    return Path(root.value) / DEAL.value


# ---- Minor 1: open() 뒤 청크를 읽지 않고 버려도 fd가 남지 않는다 ----


async def test_opening_a_file_and_dropping_it_unread_leaves_no_descriptor_open(
    root: StoragePath,
) -> None:
    storage, location = LocalFileStorage(), _location()
    await storage.save(root, location, BytesSource(b"data"), max_bytes=100)
    before = _open_descriptors()

    for _ in range(30):
        opened = await storage.open(root, location)
        assert opened.size == 4
        del opened

    assert _open_descriptors() <= before


async def test_a_fully_read_download_leaves_no_descriptor_open(root: StoragePath) -> None:
    storage, location = LocalFileStorage(), _location()
    await storage.save(root, location, BytesSource(b"data" * 1000), max_bytes=10_000)
    before = _open_descriptors()

    for _ in range(10):
        opened = await storage.open(root, location)
        assert b"".join([chunk async for chunk in opened.chunks]) == b"data" * 1000

    assert _open_descriptors() <= before


# ---- Minor 2: 읽을 수 없음(권한·IO 오류)은 "파일 없음"과 다른 오류다 ----


async def test_a_file_that_cannot_be_examined_raises_not_readable_not_missing(
    root: StoragePath,
) -> None:
    location = _location()
    _deal_dir(root).mkdir(parents=True)
    broken = _deal_dir(root) / location.key
    broken.symlink_to(broken.name)  # 자기 자신을 가리키는 링크: stat이 ELOOP로 실패한다

    with pytest.raises(StorageNotReadableError):
        await LocalFileStorage().open(root, location)


async def test_a_read_error_while_examining_the_file_is_not_reported_as_missing(
    root: StoragePath, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage, location = LocalFileStorage(), _location()
    await storage.save(root, location, BytesSource(b"data"), max_bytes=100)

    def denied(_path: Path) -> int | None:
        raise PermissionError(errno.EACCES, "denied")

    monkeypatch.setattr(_io, "stat_regular_file", denied)

    with pytest.raises(StorageNotReadableError):
        await storage.open(root, location)


async def test_a_missing_file_a_missing_deal_directory_and_a_blocked_directory_are_still_missing(
    root: StoragePath,
) -> None:
    storage = LocalFileStorage()
    with pytest.raises(StoredFileMissingError):  # root 자체가 없다
        await storage.open(root, _location())
    _deal_dir(root).parent.mkdir(parents=True)
    _deal_dir(root).write_bytes(b"a regular file where the deal directory should be")
    with pytest.raises(StoredFileMissingError):  # Deal 디렉터리 자리에 일반 파일
        await storage.open(root, _location())


async def test_the_unreadable_error_is_not_a_missing_error() -> None:
    assert not issubclass(StorageNotReadableError, StoredFileMissingError)
    assert not issubclass(StoredFileMissingError, StorageNotReadableError)


# ---- Minor 3: 저장 도중 실패하면 부분 파일이 남지 않는다 ----


async def test_a_source_that_fails_midway_leaves_no_partial_file(root: StoragePath) -> None:
    location = _location()

    with pytest.raises(ClientGone):
        await LocalFileStorage().save(
            root,
            location,
            FailingSource(ClientGone(), good_chunks=3),
            max_bytes=1_000_000,
        )

    assert not (_deal_dir(root) / location.key).exists()
    assert [child.name for child in _deal_dir(root).iterdir()] == []


async def test_an_os_error_from_the_source_becomes_not_writable_and_leaves_no_file(
    root: StoragePath,
) -> None:
    location = _location()

    with pytest.raises(StorageNotWritableError):
        await LocalFileStorage().save(
            root,
            location,
            FailingSource(OSError(errno.ECONNRESET, "reset"), good_chunks=2),
            max_bytes=1_000_000,
        )

    assert [child.name for child in _deal_dir(root).iterdir()] == []


async def test_a_write_error_becomes_not_writable_and_leaves_no_file_or_descriptor(
    root: StoragePath, monkeypatch: pytest.MonkeyPatch
) -> None:
    location = _location()
    before = _open_descriptors()

    def disk_full(_descriptor: int, _data: bytes) -> None:
        raise OSError(errno.ENOSPC, "no space left on device")

    monkeypatch.setattr(_io, "write_all", disk_full)

    with pytest.raises(StorageNotWritableError):
        await LocalFileStorage().save(root, location, BytesSource(b"x" * 4096), max_bytes=100_000)

    assert [child.name for child in _deal_dir(root).iterdir()] == []
    assert _open_descriptors() <= before


async def test_a_failed_save_does_not_block_saving_again_with_the_same_key(
    root: StoragePath,
) -> None:
    storage, location = LocalFileStorage(), _location()
    with pytest.raises(ClientGone):
        await storage.save(root, location, FailingSource(ClientGone()), max_bytes=1_000_000)

    saved = await storage.save(root, location, BytesSource(b"retry"), max_bytes=100)

    assert saved == 5
    assert (_deal_dir(root) / location.key).read_bytes() == b"retry"
