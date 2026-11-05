"""LocalFileStorage의 폴더 경로(AC32·AC33·AC36): 중첩 폴더 저장, 조각 검증, 중간 심볼릭 링크 방어.

모두 tmp_path 아래 실제 디렉터리에서 돈다(DB 불필요). 공통 계약(저장·열기·삭제·폴더 삭제)은
tests/unit/repositories/test_file_storage_*_contract.py가 Fake와 함께 맡는다.
"""

import stat
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.ports.file_storage import StorageNotWritableError, StoredFileMissingError
from app.domain.storage.path import StoragePath
from app.infra.storage.local_file_storage import LocalFileStorage
from tests.fakes.file_storage import BytesSource, folder_of, location_in

if TYPE_CHECKING:
    from app.application.ports.file_storage import StorageFolder, StoredFileLocation


def _contract_folder() -> StorageFolder:
    return folder_of("license-contracts", "7")


@pytest.fixture
def root(tmp_path: Path) -> StoragePath:
    return StoragePath.parse(str(tmp_path / "files"))


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _read(path: Path) -> bytes:
    return path.read_bytes()


def _write(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _link(link: Path, target: Path) -> None:
    link.symlink_to(target, target_is_directory=True)


def _exists(path: Path) -> bool:
    return path.exists()


def _is_dir(path: Path) -> bool:
    return path.is_dir()


def _is_link(path: Path) -> bool:
    return path.is_symlink()


def _names(path: Path) -> list[str]:
    return sorted(p.name for p in path.rglob("*"))


def _location(folder: StorageFolder | None = None) -> StoredFileLocation:
    return location_in(folder or _contract_folder(), uuid4().hex)


def _outside(tmp_path: Path) -> Path:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_bytes(b"keep")
    return outside


async def test_save_creates_the_nested_folder_path_and_writes_the_file(root: StoragePath) -> None:
    location = _location()

    written = await LocalFileStorage().save(root, location, BytesSource(b"nested"), max_bytes=100)

    assert written == len(b"nested")
    path = Path(root.value) / "license-contracts" / "7" / location.key
    assert _read(path) == b"nested"


async def test_nested_folders_and_the_file_are_closed_to_other_users(root: StoragePath) -> None:
    location = _location()

    await LocalFileStorage().save(root, location, BytesSource(b"secret"), max_bytes=100)

    base = Path(root.value) / "license-contracts"
    assert _mode(base) == 0o750
    assert _mode(base / "7") == 0o750
    assert _mode(base / "7" / location.key) == 0o640


async def test_open_reads_back_a_file_saved_in_a_nested_folder(root: StoragePath) -> None:
    storage = LocalFileStorage()
    location = _location()
    await storage.save(root, location, BytesSource(b"round trip"), max_bytes=100)

    opened = await storage.open(root, location)

    assert b"".join([chunk async for chunk in opened.chunks]) == b"round trip"


async def test_delete_removes_only_the_file_and_keeps_the_nested_folders(root: StoragePath) -> None:
    storage = LocalFileStorage()
    location = _location()
    await storage.save(root, location, BytesSource(b"x"), max_bytes=100)

    await storage.delete(root, location)

    assert _is_dir(Path(root.value) / "license-contracts" / "7")
    assert _names(Path(root.value) / "license-contracts" / "7") == []


async def test_delete_folder_removes_the_whole_tree_and_keeps_siblings(root: StoragePath) -> None:
    storage = LocalFileStorage()
    await storage.save(root, _location(), BytesSource(b"a"), max_bytes=100)
    await storage.save(root, _location(), BytesSource(b"b"), max_bytes=100)
    sibling = _location(folder_of("license-contracts", "8"))
    await storage.save(root, sibling, BytesSource(b"s"), max_bytes=100)

    await storage.delete_folder(root, _contract_folder())

    base = Path(root.value) / "license-contracts"
    assert not _exists(base / "7")
    assert _read(base / "8" / sibling.key) == b"s"
    assert _is_dir(base)


async def test_delete_folder_of_a_missing_nested_path_passes_silently(root: StoragePath) -> None:
    await LocalFileStorage().delete_folder(root, _contract_folder())  # root도 아직 없다

    assert not _exists(Path(root.value))


async def test_delete_folder_of_the_directory_name_alone_removes_all_contract_folders(
    root: StoragePath,
) -> None:
    storage = LocalFileStorage()
    await storage.save(root, _location(), BytesSource(b"a"), max_bytes=100)

    await storage.delete_folder(
        root,
        folder_of(
            "license-contracts",
        ),
    )

    assert not _exists(Path(root.value) / "license-contracts")


@pytest.mark.parametrize(
    "part",
    ["..", ".", ".x", "a/b", "a\\b", "", "a" * 65, "a\x00b", "a b", "-.", "x.y"],
)
async def test_save_rejects_a_folder_part_that_is_not_alphanumeric_or_dash(
    root: StoragePath, part: str
) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        await LocalFileStorage().save(
            root,
            _location(folder_of("license-contracts", part)),
            BytesSource(b"x"),
            max_bytes=100,
        )

    assert not _exists(Path(root.value) / "license-contracts")  # 검증이 먼저라 아무것도 안 만든다


@pytest.mark.parametrize("part", ["..", ".x", "a/b", "", "a" * 65, "a\x00b"])
async def test_delete_folder_rejects_a_folder_part_that_is_not_allowed(
    root: StoragePath, tmp_path: Path, part: str
) -> None:
    outside = _outside(tmp_path)
    _mkdir(Path(root.value))

    with pytest.raises(ValueError):  # noqa: PT011
        await LocalFileStorage().delete_folder(
            root,
            folder_of(
                part,
            ),
        )

    assert _read(outside / "precious.txt") == b"keep"
    assert _is_dir(Path(root.value))


@pytest.mark.parametrize("part", ["a", "A1", "20261016-A001", "-", "7", "a" * 64])
async def test_folder_parts_made_of_letters_digits_and_dash_are_accepted(
    root: StoragePath, part: str
) -> None:
    location = _location(
        folder_of(
            part,
        )
    )

    await LocalFileStorage().save(root, location, BytesSource(b"ok"), max_bytes=100)

    assert (Path(root.value) / part / location.key).read_bytes() == b"ok"


async def test_save_rejects_a_symlinked_intermediate_folder_and_writes_nothing_outside(
    root: StoragePath, tmp_path: Path
) -> None:
    outside = _outside(tmp_path)
    _mkdir(Path(root.value))
    _link(Path(root.value) / "license-contracts", outside)

    with pytest.raises(StorageNotWritableError):
        await LocalFileStorage().save(root, _location(), BytesSource(b"x"), max_bytes=100)

    assert _names(outside) == ["precious.txt"]


async def test_save_rejects_a_symlinked_last_folder_and_writes_nothing_outside(
    root: StoragePath, tmp_path: Path
) -> None:
    outside = _outside(tmp_path)
    _mkdir(Path(root.value) / "license-contracts")
    _link(Path(root.value) / "license-contracts" / "7", outside)

    with pytest.raises(StorageNotWritableError):
        await LocalFileStorage().save(root, _location(), BytesSource(b"x"), max_bytes=100)

    assert _names(outside) == ["precious.txt"]


async def test_delete_folder_with_a_symlinked_intermediate_folder_deletes_nothing(
    root: StoragePath, tmp_path: Path
) -> None:
    outside = _outside(tmp_path)
    _mkdir(outside / "7")
    _write(outside / "7" / "victim.txt", b"do not delete")
    _mkdir(Path(root.value))
    _link(Path(root.value) / "license-contracts", outside)

    await LocalFileStorage().delete_folder(root, _contract_folder())  # 오류 없이 통과한다

    assert _read(outside / "7" / "victim.txt") == b"do not delete"
    assert _read(outside / "precious.txt") == b"keep"


async def test_delete_folder_with_a_symlinked_last_folder_removes_only_the_link(
    root: StoragePath, tmp_path: Path
) -> None:
    outside = _outside(tmp_path)
    _mkdir(Path(root.value) / "license-contracts")
    link = Path(root.value) / "license-contracts" / "7"
    _link(link, outside)

    await LocalFileStorage().delete_folder(root, _contract_folder())

    assert not _is_link(link)
    assert _read(outside / "precious.txt") == b"keep"


async def test_open_with_a_symlinked_intermediate_folder_is_missing_and_reads_nothing_outside(
    root: StoragePath, tmp_path: Path
) -> None:
    outside = _outside(tmp_path)
    location = _location()
    _mkdir(outside / "7")
    _write(outside / "7" / location.key, b"secret")
    _mkdir(Path(root.value))
    _link(Path(root.value) / "license-contracts", outside)

    with pytest.raises(StoredFileMissingError):
        await LocalFileStorage().open(root, location)


async def test_open_with_a_symlinked_last_folder_is_missing_and_reads_nothing_outside(
    root: StoragePath, tmp_path: Path
) -> None:
    outside = _outside(tmp_path)
    location = _location()
    _write(outside / location.key, b"secret")
    _mkdir(Path(root.value) / "license-contracts")
    _link(Path(root.value) / "license-contracts" / "7", outside)

    with pytest.raises(StoredFileMissingError):
        await LocalFileStorage().open(root, location)


async def test_delete_with_a_symlinked_intermediate_folder_keeps_the_file_behind_the_link(
    root: StoragePath, tmp_path: Path
) -> None:
    outside = _outside(tmp_path)
    location = _location()
    _mkdir(outside / "7")
    _write(outside / "7" / location.key, b"do not delete")
    _mkdir(Path(root.value))
    _link(Path(root.value) / "license-contracts", outside)

    await LocalFileStorage().delete(root, location)  # 오류 없이 통과한다

    assert _read(outside / "7" / location.key) == b"do not delete"


async def test_delete_with_a_symlinked_last_folder_keeps_the_file_behind_the_link(
    root: StoragePath, tmp_path: Path
) -> None:
    outside = _outside(tmp_path)
    location = _location()
    _write(outside / location.key, b"do not delete")
    _mkdir(Path(root.value) / "license-contracts")
    _link(Path(root.value) / "license-contracts" / "7", outside)

    await LocalFileStorage().delete(root, location)

    assert _read(outside / location.key) == b"do not delete"
