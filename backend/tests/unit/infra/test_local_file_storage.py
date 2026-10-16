"""LocalFileStorage 고유 동작(P2b Q1): 디스크 배치 `<root>/<deal_code>/<key>`와 권한, 경로 가둠.

공통 계약(저장·열기·삭제)은 tests/unit/repositories/test_file_storage_*_contract.py가 맡는다.
모두 tmp_path 아래 실제 디렉터리에서 돈다(DB 불필요). 파일시스템 준비·확인은 동기 도우미로 한다.
"""

import contextlib
import stat
from pathlib import Path
from uuid import uuid4

import pytest
from app.application.ports.file_storage import (
    StorageNotWritableError,
    StoredFileLocation,
    StoredFileMissingError,
)
from app.domain.storage.path import StoragePath
from app.infra.storage.local_file_storage import LocalFileStorage

from app.domain.deal.code import DealCode
from tests.fakes.file_storage import BytesSource

DEAL = DealCode("20261016-A001")


def _read(path: Path) -> bytes:
    return path.read_bytes()


def _names(directory: Path) -> list[str]:
    return sorted(child.name for child in directory.iterdir())


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _make_dir(path: Path) -> None:
    path.mkdir(parents=True)


def _write(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _link_dir(link: Path, target: Path) -> None:
    link.symlink_to(target, target_is_directory=True)


def _anywhere_named(base: Path, name: str) -> bool:
    return any(found.name == name for found in base.rglob("*"))


@pytest.fixture
def root(tmp_path: Path) -> StoragePath:
    return StoragePath.parse(str(tmp_path / "files"))


def _location(key: str | None = None) -> StoredFileLocation:
    return StoredFileLocation(deal_code=DEAL, key=key or uuid4().hex)


async def test_save_writes_the_bytes_to_root_deal_code_key(root: StoragePath) -> None:
    location = _location()

    await LocalFileStorage().save(root, location, BytesSource(b"raw bytes"), max_bytes=100)

    assert _read(Path(root.value) / DEAL.value / location.key) == b"raw bytes"


async def test_the_disk_file_name_is_the_key_not_the_original_name(root: StoragePath) -> None:
    location = _location()

    await LocalFileStorage().save(root, location, BytesSource(b"x"), max_bytes=100)

    assert _names(Path(root.value) / DEAL.value) == [location.key]


async def test_saved_files_and_directories_are_closed_to_other_users(root: StoragePath) -> None:
    location = _location()

    await LocalFileStorage().save(root, location, BytesSource(b"secret"), max_bytes=100)

    deal_dir = Path(root.value) / DEAL.value
    assert _mode(deal_dir / location.key) & 0o007 == 0
    assert _mode(deal_dir) & 0o007 == 0


async def test_save_with_a_key_that_looks_like_a_traversal_writes_nothing_outside(
    root: StoragePath, tmp_path: Path
) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        await LocalFileStorage().save(
            root, _location("../../escaped"), BytesSource(b"x"), max_bytes=100
        )

    assert not _anywhere_named(tmp_path, "escaped")


async def test_save_when_the_deal_path_is_a_regular_file_raises_not_writable(
    root: StoragePath,
) -> None:
    _make_dir(Path(root.value))
    _write(Path(root.value) / DEAL.value, b"i block the deal directory")

    with pytest.raises(StorageNotWritableError):
        await LocalFileStorage().save(root, _location(), BytesSource(b"x"), max_bytes=100)


async def test_check_writable_on_a_path_that_is_a_regular_file_raises_not_writable(
    tmp_path: Path,
) -> None:
    blocker = tmp_path / "file"
    _write(blocker, b"x")

    with pytest.raises(StorageNotWritableError):
        await LocalFileStorage().check_writable(StoragePath.parse(str(blocker)))

    assert _read(blocker) == b"x"


async def test_open_streams_the_file_in_chunks_that_add_up_to_the_content(
    root: StoragePath,
) -> None:
    data = b"abcdefgh" * (400 * 1024)  # 3.2 MiB: 여러 청크
    location = _location()
    storage = LocalFileStorage()
    await storage.save(root, location, BytesSource(data), max_bytes=10 * 1024 * 1024)

    opened = await storage.open(root, location)
    chunks = [chunk async for chunk in opened.chunks]

    assert opened.size == len(data)
    assert len(chunks) > 1
    assert b"".join(chunks) == data


async def test_open_of_a_directory_instead_of_a_file_raises_missing(root: StoragePath) -> None:
    key = uuid4().hex
    _make_dir(Path(root.value) / DEAL.value / key)

    with pytest.raises(StoredFileMissingError):
        await LocalFileStorage().open(root, _location(key))


async def test_delete_deal_files_does_not_follow_a_symlink_out_of_the_root(
    root: StoragePath, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    _make_dir(outside)
    _write(outside / "precious.txt", b"keep")
    _make_dir(Path(root.value))
    _link_dir(Path(root.value) / DEAL.value, outside)

    with contextlib.suppress(
        StorageNotWritableError
    ):  # 링크를 못 지워도 좋다. 바깥만 안 지우면 된다
        await LocalFileStorage().delete_deal_files(root, DEAL)

    assert _read(outside / "precious.txt") == b"keep"
