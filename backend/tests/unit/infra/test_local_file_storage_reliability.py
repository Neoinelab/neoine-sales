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
from tests.fakes.file_storage import BytesSource, deal_location
from tests.fakes.sources import ClientGone, FailingSource

DEAL = DealCode("20261016-A001")


def _open_descriptors() -> int:
    gc.collect()
    return len(os.listdir("/dev/fd"))


@pytest.fixture
def root(tmp_path: Path) -> StoragePath:
    return StoragePath.parse(str(tmp_path / "files"))


def _location() -> StoredFileLocation:
    return deal_location(DEAL, uuid4().hex)


def _deal_dir(root: StoragePath) -> Path:
    return Path(root.value) / DEAL.value


# ---- Minor 1: open() 뒤 청크를 읽지 않고 버려도 fd가 남지 않는다 ----


async def test_opening_a_file_and_dropping_it_unread_leaves_no_descriptor_open(
    root: StoragePath,
) -> None:
    """열고 읽지 않은 채 버려도 파일 디스크립터가 남지 않는다."""
    # given: 저장된 파일과 현재 열린 디스크립터 수
    storage, location = LocalFileStorage(), _location()
    await storage.save(root, location, BytesSource(b"data"), max_bytes=100)
    before = _open_descriptors()

    # when: 파일을 열고 읽지 않은 채 버린다
    for _ in range(30):
        opened = await storage.open(root, location)
        assert opened.size == 4
        del opened

    # then: 열린 디스크립터가 늘지 않았다
    assert _open_descriptors() <= before


async def test_a_fully_read_download_leaves_no_descriptor_open(root: StoragePath) -> None:
    """끝까지 읽은 다운로드는 디스크립터를 남기지 않는다."""
    # given: 저장된 파일과 현재 열린 디스크립터 수
    storage, location = LocalFileStorage(), _location()
    await storage.save(root, location, BytesSource(b"data" * 1000), max_bytes=10_000)
    before = _open_descriptors()

    # when: 파일을 열어 끝까지 읽는다
    for _ in range(10):
        opened = await storage.open(root, location)
        assert b"".join([chunk async for chunk in opened.chunks]) == b"data" * 1000

    # then: 열린 디스크립터가 늘지 않았다
    assert _open_descriptors() <= before


# ---- Minor 2: 읽을 수 없음(권한·IO 오류)은 "파일 없음"과 다른 오류다 ----


async def test_a_file_that_cannot_be_examined_raises_not_readable_not_missing(
    root: StoragePath,
) -> None:
    """상태를 확인할 수 없는 파일은 파일 없음이 아니라 읽기 불가 오류다."""
    # given: 자기 자신을 가리키는 심볼릭 링크 파일
    location = _location()
    _deal_dir(root).mkdir(parents=True)
    broken = _deal_dir(root) / location.key
    broken.symlink_to(broken.name)  # 자기 자신을 가리키는 링크: stat이 ELOOP로 실패한다

    # when·then: 열면 읽기 불가 오류다
    with pytest.raises(StorageNotReadableError):
        await LocalFileStorage().open(root, location)


async def test_a_read_error_while_examining_the_file_is_not_reported_as_missing(
    root: StoragePath, monkeypatch: pytest.MonkeyPatch
) -> None:
    """확인 중 읽기 오류는 파일 없음으로 보고하지 않는다."""
    # given: 저장된 파일과 권한 오류를 내도록 바꾼 상태 확인
    storage, location = LocalFileStorage(), _location()
    await storage.save(root, location, BytesSource(b"data"), max_bytes=100)

    def denied(_path: Path) -> int | None:
        raise PermissionError(errno.EACCES, "denied")

    monkeypatch.setattr(_io, "stat_regular_file", denied)

    # when·then: 열면 읽기 불가 오류다
    with pytest.raises(StorageNotReadableError):
        await storage.open(root, location)


async def test_a_missing_file_a_missing_deal_directory_and_a_blocked_directory_are_still_missing(
    root: StoragePath,
) -> None:
    """루트·Deal 폴더가 없거나 폴더 자리가 일반 파일이면 여전히 파일 없음이다."""
    # given: 루트가 없는 저장소
    storage = LocalFileStorage()

    # when·then: 루트가 없는 채로 열면 파일 없음 오류다
    with pytest.raises(StoredFileMissingError):  # root 자체가 없다
        await storage.open(root, _location())
    _deal_dir(root).parent.mkdir(parents=True)
    _deal_dir(root).write_bytes(b"a regular file where the deal directory should be")
    # when·then: Deal 폴더 자리에 일반 파일이 있어도 파일 없음 오류다
    with pytest.raises(StoredFileMissingError):  # Deal 디렉터리 자리에 일반 파일
        await storage.open(root, _location())


async def test_the_unreadable_error_is_not_a_missing_error() -> None:
    """읽기 불가 오류와 파일 없음 오류는 서로 다른 계열이다."""
    # when·then: 어느 쪽도 상대의 하위 클래스가 아니다
    assert not issubclass(StorageNotReadableError, StoredFileMissingError)
    assert not issubclass(StoredFileMissingError, StorageNotReadableError)


# ---- Minor 3: 저장 도중 실패하면 부분 파일이 남지 않는다 ----


async def test_a_source_that_fails_midway_leaves_no_partial_file(root: StoragePath) -> None:
    """원본이 중간에 실패하면 부분 파일이 남지 않는다."""
    # given: 새 저장 위치
    location = _location()

    # when·then: 중간에 실패하는 원본을 저장하면 그 오류다
    with pytest.raises(ClientGone):
        await LocalFileStorage().save(
            root,
            location,
            FailingSource(ClientGone(), good_chunks=3),
            max_bytes=1_000_000,
        )

    # then: 파일도 폴더 항목도 남지 않는다
    assert not (_deal_dir(root) / location.key).exists()
    assert [child.name for child in _deal_dir(root).iterdir()] == []


async def test_an_os_error_from_the_source_becomes_not_writable_and_leaves_no_file(
    root: StoragePath,
) -> None:
    """원본의 OS 오류는 쓰기 불가 오류가 되고 파일이 남지 않는다."""
    # given: 새 저장 위치
    location = _location()

    # when·then: 연결 리셋 OS 오류를 내는 원본을 저장하면 쓰기 불가 오류다
    with pytest.raises(StorageNotWritableError):
        await LocalFileStorage().save(
            root,
            location,
            FailingSource(OSError(errno.ECONNRESET, "reset"), good_chunks=2),
            max_bytes=1_000_000,
        )

    # then: Deal 폴더가 비어 있다
    assert [child.name for child in _deal_dir(root).iterdir()] == []


async def test_a_write_error_becomes_not_writable_and_leaves_no_file_or_descriptor(
    root: StoragePath, monkeypatch: pytest.MonkeyPatch
) -> None:
    """쓰기 오류는 쓰기 불가 오류가 되고 파일·디스크립터가 남지 않는다."""
    # given: 새 위치와 디스크가 가득 찬 것처럼 만든 쓰기
    location = _location()
    before = _open_descriptors()

    def disk_full(_descriptor: int, _data: bytes) -> None:
        raise OSError(errno.ENOSPC, "no space left on device")

    monkeypatch.setattr(_io, "write_all", disk_full)

    # when·then: 저장하면 쓰기 불가 오류다
    with pytest.raises(StorageNotWritableError):
        await LocalFileStorage().save(root, location, BytesSource(b"x" * 4096), max_bytes=100_000)

    # then: Deal 폴더가 비어 있고 디스크립터가 늘지 않았다
    assert [child.name for child in _deal_dir(root).iterdir()] == []
    assert _open_descriptors() <= before


async def test_a_failed_save_does_not_block_saving_again_with_the_same_key(
    root: StoragePath,
) -> None:
    """저장이 실패해도 같은 키로 다시 저장할 수 있다."""
    # given: 같은 키로 저장이 실패했다
    storage, location = LocalFileStorage(), _location()
    with pytest.raises(ClientGone):
        await storage.save(root, location, FailingSource(ClientGone()), max_bytes=1_000_000)

    # when: 같은 키로 다시 저장한다
    saved = await storage.save(root, location, BytesSource(b"retry"), max_bytes=100)

    # then: 저장되어 내용이 새 바이트다
    assert saved == 5
    assert (_deal_dir(root) / location.key).read_bytes() == b"retry"
