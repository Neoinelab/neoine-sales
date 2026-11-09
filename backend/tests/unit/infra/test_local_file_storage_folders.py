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
    """중첩 폴더 위치에 저장하면 폴더를 만들고 파일을 쓴다.

    테스트 코드: LC-063
    """
    # given: license-contracts/7 폴더 위치
    location = _location()

    # when: 파일을 저장한다
    written = await LocalFileStorage().save(root, location, BytesSource(b"nested"), max_bytes=100)

    # then: 쓴 바이트 수와 파일 내용이 맞다
    assert written == len(b"nested")
    path = Path(root.value) / "license-contracts" / "7" / location.key
    assert _read(path) == b"nested"


async def test_nested_folders_and_the_file_are_closed_to_other_users(root: StoragePath) -> None:
    """중첩 폴더는 750, 파일은 640 권한으로 만들어진다."""
    # given: license-contracts/7 폴더 위치
    location = _location()

    # when: 파일을 저장한다
    await LocalFileStorage().save(root, location, BytesSource(b"secret"), max_bytes=100)

    base = Path(root.value) / "license-contracts"
    # then: 폴더 권한 0o750, 파일 권한 0o640
    assert _mode(base) == 0o750
    assert _mode(base / "7") == 0o750
    assert _mode(base / "7" / location.key) == 0o640


async def test_open_reads_back_a_file_saved_in_a_nested_folder(root: StoragePath) -> None:
    """중첩 폴더에 저장한 파일을 열어 같은 내용을 읽는다.

    테스트 코드: LC-074
    """
    # given: 중첩 폴더에 저장한 파일
    storage = LocalFileStorage()
    location = _location()
    await storage.save(root, location, BytesSource(b"round trip"), max_bytes=100)

    # when: 파일을 연다
    opened = await storage.open(root, location)

    # then: 저장한 내용이 그대로 읽힌다
    assert b"".join([chunk async for chunk in opened.chunks]) == b"round trip"


async def test_delete_removes_only_the_file_and_keeps_the_nested_folders(root: StoragePath) -> None:
    """파일 삭제는 파일만 지우고 중첩 폴더는 남긴다.

    테스트 코드: LC-076
    """
    # given: 중첩 폴더에 저장한 파일
    storage = LocalFileStorage()
    location = _location()
    await storage.save(root, location, BytesSource(b"x"), max_bytes=100)

    # when: 파일을 삭제한다
    await storage.delete(root, location)

    # then: 폴더는 있고 비어 있다
    assert _is_dir(Path(root.value) / "license-contracts" / "7")
    assert _names(Path(root.value) / "license-contracts" / "7") == []


async def test_delete_folder_removes_the_whole_tree_and_keeps_siblings(root: StoragePath) -> None:
    """폴더 삭제는 그 트리 전체를 지우고 형제 폴더는 남긴다.

    테스트 코드: LC-058
    """
    # given: 계약 폴더 7에 파일 둘, 형제 폴더 8에 파일 하나
    storage = LocalFileStorage()
    await storage.save(root, _location(), BytesSource(b"a"), max_bytes=100)
    await storage.save(root, _location(), BytesSource(b"b"), max_bytes=100)
    sibling = _location(folder_of("license-contracts", "8"))
    await storage.save(root, sibling, BytesSource(b"s"), max_bytes=100)

    await storage.delete_folder(root, _contract_folder())

    # when: 계약 폴더 7을 삭제한다
    base = Path(root.value) / "license-contracts"
    # then: 7은 통째로 없고 8은 그대로다
    assert not _exists(base / "7")
    assert _read(base / "8" / sibling.key) == b"s"
    assert _is_dir(base)


async def test_delete_folder_of_a_missing_nested_path_passes_silently(root: StoragePath) -> None:
    """없는 폴더의 삭제는 오류 없이 통과한다.

    테스트 코드: LC-062
    """
    # given: 아직 만들어지지 않은 저장 위치
    # when: 없는 계약 폴더를 삭제한다
    await LocalFileStorage().delete_folder(root, _contract_folder())  # root도 아직 없다

    # then: 오류가 없고 저장 위치도 만들어지지 않는다
    assert not _exists(Path(root.value))


async def test_delete_folder_of_the_directory_name_alone_removes_all_contract_folders(
    root: StoragePath,
) -> None:
    """디렉터리 이름만으로 삭제하면 모든 계약 폴더가 지워진다.

    테스트 코드: LC-080
    """
    # given: 계약 폴더에 파일이 있다
    storage = LocalFileStorage()
    await storage.save(root, _location(), BytesSource(b"a"), max_bytes=100)

    # when: license-contracts 폴더를 삭제한다
    await storage.delete_folder(
        root,
        folder_of(
            "license-contracts",
        ),
    )

    # then: license-contracts 폴더가 없다
    assert not _exists(Path(root.value) / "license-contracts")


@pytest.mark.parametrize(
    "part",
    ["..", ".", ".x", "a/b", "a\\b", "", "a" * 65, "a\x00b", "a b", "-.", "x.y"],
)
async def test_save_rejects_a_folder_part_that_is_not_alphanumeric_or_dash(
    root: StoragePath, part: str
) -> None:
    """폴더 조각이 영문·숫자·대시가 아니면 저장이 거절된다."""
    # when: 허용되지 않는 폴더 조각으로 저장한다
    with pytest.raises(ValueError):  # noqa: PT011
        await LocalFileStorage().save(
            root,
            _location(folder_of("license-contracts", part)),
            BytesSource(b"x"),
            max_bytes=100,
        )

    # then: ValueError이고 아무것도 만들어지지 않는다
    assert not _exists(Path(root.value) / "license-contracts")  # 검증이 먼저라 아무것도 안 만든다


@pytest.mark.parametrize("part", ["..", ".x", "a/b", "", "a" * 65, "a\x00b"])
async def test_delete_folder_rejects_a_folder_part_that_is_not_allowed(
    root: StoragePath, tmp_path: Path, part: str
) -> None:
    """허용되지 않는 폴더 조각의 삭제는 거절되고 바깥 파일은 안전하다."""
    # given: 저장 위치 바깥의 파일
    outside = _outside(tmp_path)
    _mkdir(Path(root.value))

    # when: 저장 위치 밖을 가리키는 조각으로 폴더를 삭제한다
    with pytest.raises(ValueError):  # noqa: PT011
        await LocalFileStorage().delete_folder(
            root,
            folder_of(
                part,
            ),
        )

    # then: ValueError이고 바깥 파일과 저장 위치가 그대로다
    assert _read(outside / "precious.txt") == b"keep"
    assert _is_dir(Path(root.value))


@pytest.mark.parametrize("part", ["a", "A1", "20261016-A001", "-", "7", "a" * 64])
async def test_folder_parts_made_of_letters_digits_and_dash_are_accepted(
    root: StoragePath, part: str
) -> None:
    """영문·숫자·대시로 된 폴더 조각은 허용된다."""
    # given: 허용되는 조각의 폴더 위치
    location = _location(
        folder_of(
            part,
        )
    )

    # when: 파일을 저장한다
    await LocalFileStorage().save(root, location, BytesSource(b"ok"), max_bytes=100)

    # then: 그 폴더에 파일이 쓰인다
    assert (Path(root.value) / part / location.key).read_bytes() == b"ok"


async def test_save_rejects_a_symlinked_intermediate_folder_and_writes_nothing_outside(
    root: StoragePath, tmp_path: Path
) -> None:
    """중간 폴더가 심볼릭 링크면 저장을 거절하고 바깥에 쓰지 않는다."""
    # given: license-contracts가 바깥 폴더를 가리키는 링크
    outside = _outside(tmp_path)
    _mkdir(Path(root.value))
    _link(Path(root.value) / "license-contracts", outside)

    # when: 파일을 저장한다
    with pytest.raises(StorageNotWritableError):
        await LocalFileStorage().save(root, _location(), BytesSource(b"x"), max_bytes=100)

    # then: StorageNotWritableError, 바깥 폴더 내용 그대로
    assert _names(outside) == ["precious.txt"]


async def test_save_rejects_a_symlinked_last_folder_and_writes_nothing_outside(
    root: StoragePath, tmp_path: Path
) -> None:
    """마지막 폴더가 심볼릭 링크면 저장을 거절하고 바깥에 쓰지 않는다."""
    # given: 계약 폴더가 바깥 폴더를 가리키는 링크
    outside = _outside(tmp_path)
    _mkdir(Path(root.value) / "license-contracts")
    _link(Path(root.value) / "license-contracts" / "7", outside)

    # when: 파일을 저장한다
    with pytest.raises(StorageNotWritableError):
        await LocalFileStorage().save(root, _location(), BytesSource(b"x"), max_bytes=100)

    # then: StorageNotWritableError, 바깥 폴더 내용 그대로
    assert _names(outside) == ["precious.txt"]


async def test_delete_folder_with_a_symlinked_intermediate_folder_deletes_nothing(
    root: StoragePath, tmp_path: Path
) -> None:
    """중간 폴더가 링크면 폴더 삭제는 아무것도 지우지 않는다."""
    # given: license-contracts가 바깥 폴더를 가리키는 링크
    outside = _outside(tmp_path)
    _mkdir(outside / "7")
    _write(outside / "7" / "victim.txt", b"do not delete")
    _mkdir(Path(root.value))
    _link(Path(root.value) / "license-contracts", outside)

    # when: 계약 폴더를 삭제한다
    await LocalFileStorage().delete_folder(root, _contract_folder())  # 오류 없이 통과한다

    # then: 오류 없이 통과하고 바깥 파일은 그대로다
    assert _read(outside / "7" / "victim.txt") == b"do not delete"
    assert _read(outside / "precious.txt") == b"keep"


async def test_delete_folder_with_a_symlinked_last_folder_removes_only_the_link(
    root: StoragePath, tmp_path: Path
) -> None:
    """마지막 폴더가 링크면 링크만 지우고 바깥은 건드리지 않는다."""
    # given: 계약 폴더가 바깥 폴더를 가리키는 링크
    outside = _outside(tmp_path)
    _mkdir(Path(root.value) / "license-contracts")
    link = Path(root.value) / "license-contracts" / "7"
    _link(link, outside)

    # when: 계약 폴더를 삭제한다
    await LocalFileStorage().delete_folder(root, _contract_folder())

    # then: 링크는 없고 바깥 파일은 그대로다
    assert not _is_link(link)
    assert _read(outside / "precious.txt") == b"keep"


async def test_open_with_a_symlinked_intermediate_folder_is_missing_and_reads_nothing_outside(
    root: StoragePath, tmp_path: Path
) -> None:
    """중간 폴더가 링크면 열기는 없는 파일로 처리하고 바깥을 읽지 않는다.

    테스트 코드: LC-075
    """
    # given: license-contracts가 바깥 폴더를 가리키는 링크
    outside = _outside(tmp_path)
    location = _location()
    _mkdir(outside / "7")
    _write(outside / "7" / location.key, b"secret")
    _mkdir(Path(root.value))
    _link(Path(root.value) / "license-contracts", outside)

    # when: 파일을 연다
    with pytest.raises(StoredFileMissingError):
        await LocalFileStorage().open(root, location)
    # then: StoredFileMissingError


async def test_open_with_a_symlinked_last_folder_is_missing_and_reads_nothing_outside(
    root: StoragePath, tmp_path: Path
) -> None:
    """마지막 폴더가 링크면 열기는 없는 파일로 처리하고 바깥을 읽지 않는다.

    테스트 코드: LC-075
    """
    # given: 계약 폴더가 바깥 폴더를 가리키는 링크
    outside = _outside(tmp_path)
    location = _location()
    _write(outside / location.key, b"secret")
    _mkdir(Path(root.value) / "license-contracts")
    _link(Path(root.value) / "license-contracts" / "7", outside)

    # when: 파일을 연다
    with pytest.raises(StoredFileMissingError):
        await LocalFileStorage().open(root, location)
    # then: StoredFileMissingError


async def test_delete_with_a_symlinked_intermediate_folder_keeps_the_file_behind_the_link(
    root: StoragePath, tmp_path: Path
) -> None:
    """중간 폴더가 링크면 파일 삭제는 링크 뒤 파일을 지우지 않는다."""
    # given: license-contracts가 바깥 폴더를 가리키는 링크
    outside = _outside(tmp_path)
    location = _location()
    _mkdir(outside / "7")
    _write(outside / "7" / location.key, b"do not delete")
    _mkdir(Path(root.value))
    _link(Path(root.value) / "license-contracts", outside)

    # when: 파일을 삭제한다
    await LocalFileStorage().delete(root, location)  # 오류 없이 통과한다

    # then: 오류 없이 통과하고 링크 뒤 파일은 그대로다
    assert _read(outside / "7" / location.key) == b"do not delete"


async def test_delete_with_a_symlinked_last_folder_keeps_the_file_behind_the_link(
    root: StoragePath, tmp_path: Path
) -> None:
    """마지막 폴더가 링크면 파일 삭제는 링크 뒤 파일을 지우지 않는다."""
    # given: 계약 폴더가 바깥 폴더를 가리키는 링크
    outside = _outside(tmp_path)
    location = _location()
    _write(outside / location.key, b"do not delete")
    _mkdir(Path(root.value) / "license-contracts")
    _link(Path(root.value) / "license-contracts" / "7", outside)

    # when: 파일을 삭제한다
    await LocalFileStorage().delete(root, location)

    # then: 링크 뒤 파일은 그대로다
    assert _read(outside / location.key) == b"do not delete"
