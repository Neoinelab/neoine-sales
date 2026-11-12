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
from app.domain.deal.code import DealCode
from app.domain.storage.path import StoragePath
from app.infra.storage.local_file_storage import LocalFileStorage
from tests.fakes.file_storage import BytesSource, deal_folder_of, deal_location

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
    return deal_location(DEAL, key or uuid4().hex)


async def test_save_writes_the_bytes_to_root_deal_code_key(root: StoragePath) -> None:
    """저장하면 `<root>/<deal_code>/<key>`에 바이트가 그대로 쓰인다."""
    # given: 새 저장 위치
    location = _location()

    # when: 파일을 저장한다
    await LocalFileStorage().save(root, location, BytesSource(b"raw bytes"), max_bytes=100)

    # then: 해당 경로의 내용이 저장한 바이트다
    assert _read(Path(root.value) / DEAL.value / location.key) == b"raw bytes"


async def test_the_disk_file_name_is_the_key_not_the_original_name(root: StoragePath) -> None:
    """디스크 파일 이름은 원래 이름이 아니라 키다."""
    # given: 새 저장 위치
    location = _location()

    # when: 파일을 저장한다
    await LocalFileStorage().save(root, location, BytesSource(b"x"), max_bytes=100)

    # then: Deal 폴더에는 그 키 이름의 파일 하나뿐이다
    assert _names(Path(root.value) / DEAL.value) == [location.key]


async def test_saved_files_and_directories_are_closed_to_other_users(root: StoragePath) -> None:
    """저장한 파일과 폴더는 다른 사용자에게 닫혀 있다."""
    # given: 새 저장 위치
    location = _location()

    # when: 파일을 저장한다
    await LocalFileStorage().save(root, location, BytesSource(b"secret"), max_bytes=100)

    # then: 파일과 폴더 모두 others 권한 비트가 없다
    deal_dir = Path(root.value) / DEAL.value
    assert _mode(deal_dir / location.key) & 0o007 == 0
    assert _mode(deal_dir) & 0o007 == 0


async def test_save_with_a_key_that_looks_like_a_traversal_writes_nothing_outside(
    root: StoragePath, tmp_path: Path
) -> None:
    """경로 이탈처럼 보이는 키는 바깥에 아무것도 쓰지 않는다."""
    # when·then: "../../escaped" 키로 저장하면 오류다
    with pytest.raises(ValueError):  # noqa: PT011
        await LocalFileStorage().save(
            root, _location("../../escaped"), BytesSource(b"x"), max_bytes=100
        )

    # then: 저장소 바깥을 포함해 그 이름의 파일이 없다
    assert not _anywhere_named(tmp_path, "escaped")


async def test_save_when_the_deal_path_is_a_regular_file_raises_not_writable(
    root: StoragePath,
) -> None:
    """Deal 폴더 자리가 일반 파일이면 쓰기 불가 오류다."""
    # given: Deal 폴더 자리를 일반 파일이 막고 있다
    _make_dir(Path(root.value))
    _write(Path(root.value) / DEAL.value, b"i block the deal directory")

    # when·then: 저장하면 쓰기 불가 오류다
    with pytest.raises(StorageNotWritableError):
        await LocalFileStorage().save(root, _location(), BytesSource(b"x"), max_bytes=100)


async def test_check_writable_on_a_path_that_is_a_regular_file_raises_not_writable(
    tmp_path: Path,
) -> None:
    """일반 파일 경로의 쓰기 확인은 쓰기 불가 오류이고 파일은 그대로다."""
    # given: 일반 파일이 있는 경로
    blocker = tmp_path / "file"
    _write(blocker, b"x")

    # when·then: 쓰기 확인을 하면 쓰기 불가 오류다
    with pytest.raises(StorageNotWritableError):
        await LocalFileStorage().check_writable(StoragePath.parse(str(blocker)))

    # then: 파일 내용이 그대로다
    assert _read(blocker) == b"x"


async def test_open_streams_the_file_in_chunks_that_add_up_to_the_content(
    root: StoragePath,
) -> None:
    """큰 파일은 여러 청크로 흘러가고 합치면 원래 내용이다.

    테스트 코드: AT-032
    """
    # given: 3.2MiB 파일을 저장해 둔다
    data = b"abcdefgh" * (400 * 1024)  # 3.2 MiB: 여러 청크
    location = _location()
    storage = LocalFileStorage()
    await storage.save(root, location, BytesSource(data), max_bytes=10 * 1024 * 1024)

    # when: 파일을 열어 청크를 읽는다
    opened = await storage.open(root, location)
    chunks = [chunk async for chunk in opened.chunks]

    # then: 크기가 같고 청크가 여럿이며 합치면 원래 내용이다
    assert opened.size == len(data)
    assert len(chunks) > 1
    assert b"".join(chunks) == data


async def test_open_of_a_directory_instead_of_a_file_raises_missing(root: StoragePath) -> None:
    """파일 자리에 폴더가 있으면 파일 없음 오류다."""
    # given: 키 이름의 폴더
    key = uuid4().hex
    _make_dir(Path(root.value) / DEAL.value / key)

    # when·then: 그 위치를 열면 파일 없음 오류다
    with pytest.raises(StoredFileMissingError):
        await LocalFileStorage().open(root, _location(key))


async def test_delete_folder_does_not_follow_a_symlink_out_of_the_root(
    root: StoragePath, tmp_path: Path
) -> None:
    """폴더 삭제는 심볼릭 링크를 따라 루트 밖을 지우지 않는다."""
    # given: 루트 밖 폴더와 Deal 폴더 자리의 심볼릭 링크
    outside = tmp_path / "outside"
    _make_dir(outside)
    _write(outside / "precious.txt", b"keep")
    _make_dir(Path(root.value))
    _link_dir(Path(root.value) / DEAL.value, outside)

    # when: Deal 폴더를 삭제한다
    with contextlib.suppress(
        StorageNotWritableError
    ):  # 링크를 못 지워도 좋다. 바깥만 안 지우면 된다
        await LocalFileStorage().delete_folder(root, deal_folder_of(DEAL))

    # then: 루트 밖 파일이 그대로 있다
    assert _read(outside / "precious.txt") == b"keep"
