"""FileStorage 폴더 계약: 중첩 폴더 저장·열기·삭제와 조각 검증. Fake·Local 공통.

심볼릭 링크 방어는 실제 파일시스템이 필요해 infra/test_local_file_storage_folders.py가 맡는다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.ports.file_storage import StoredFileMissingError
from tests.fakes.file_storage import BytesSource, folder_of, location_in

if TYPE_CHECKING:
    from app.application.ports.file_storage import StorageFolder, StoredFileLocation
    from tests.unit.repositories.file_storage_case import FileStorageCase


def _c7() -> StorageFolder:
    return folder_of("license-contracts", "7")


def _c8() -> StorageFolder:
    return folder_of("license-contracts", "8")


async def _put(
    case: FileStorageCase, folder: StorageFolder, data: bytes = b"data"
) -> StoredFileLocation:
    location = location_in(folder, uuid4().hex)
    await case.storage.save(case.root, location, BytesSource(data), max_bytes=1000)
    return location


def _path(case: FileStorageCase, folder: StorageFolder) -> str:
    return "/".join([case.root.value, *folder.parts])


async def _read(case: FileStorageCase, location: StoredFileLocation) -> bytes:
    opened = await case.storage.open(case.root, location)
    return b"".join([chunk async for chunk in opened.chunks])


async def test_save_creates_the_missing_nested_folders_and_the_file_can_be_read(
    file_case: FileStorageCase,
) -> None:
    """없는 중첩 폴더를 만들며 저장하고 파일을 읽을 수 있다."""
    # when: 없는 중첩 폴더에 파일을 저장하고 읽는다 (전제: Fake·Local 공통)
    location = await _put(file_case, _c7(), b"nested")

    content = await _read(file_case, location)

    # then: 내용이 같고 폴더 안에 그 파일만 있다
    assert content == b"nested"
    assert file_case.entries(_path(file_case, _c7())) == [location.key]
    assert file_case.entries(f"{file_case.root.value}/license-contracts") == ["7"]


async def test_the_same_key_in_different_folders_is_a_different_file(
    file_case: FileStorageCase,
) -> None:
    """폴더가 다르면 같은 키도 다른 파일이다."""
    # given: 같은 키를 쓰는 두 폴더의 위치
    key = uuid4().hex
    first = location_in(_c7(), key)
    second = location_in(_c8(), key)

    # when: 각 폴더에 다른 내용을 저장하고 읽는다 (전제: Fake·Local 공통)
    await file_case.storage.save(file_case.root, first, BytesSource(b"one"), max_bytes=10)
    await file_case.storage.save(file_case.root, second, BytesSource(b"two"), max_bytes=10)

    first_content = await _read(file_case, first)
    second_content = await _read(file_case, second)

    # then: 폴더마다 자기 내용이 읽힌다
    assert first_content == b"one"
    assert second_content == b"two"


async def test_open_in_another_folder_is_missing(file_case: FileStorageCase) -> None:
    """다른 폴더에서 열면 파일이 없다."""
    # given: 한 폴더에 저장된 파일
    location = await _put(file_case, _c7())

    # when·then: 같은 키를 다른 폴더에서 열면 StoredFileMissingError가 난다 (전제: Fake·Local 공통)
    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.root, location_in(_c8(), location.key))


async def test_delete_of_a_file_keeps_the_nested_folder(file_case: FileStorageCase) -> None:
    """파일을 삭제해도 중첩 폴더는 남는다."""
    # given: 중첩 폴더에 저장된 파일
    location = await _put(file_case, _c7())

    # when: 파일을 삭제한다 (전제: Fake·Local 공통)
    await file_case.storage.delete(file_case.root, location)

    # then: 폴더는 남고 비어 있다
    assert file_case.dir_exists(_path(file_case, _c7()))
    assert file_case.entries(_path(file_case, _c7())) == []


async def test_delete_folder_removes_the_tree_and_keeps_sibling_folders(
    file_case: FileStorageCase,
) -> None:
    """폴더 삭제는 하위 전체를 지우고 이웃 폴더는 남긴다."""
    # given: 두 폴더에 각각 저장된 파일
    gone = await _put(file_case, _c7())
    kept = await _put(file_case, _c8(), b"kept")

    # when: 한 폴더를 삭제한다 (전제: Fake·Local 공통)
    await file_case.storage.delete_folder(file_case.root, _c7())

    kept_content = await _read(file_case, kept)

    # then: 그 폴더와 파일은 사라지고 이웃 폴더 파일은 남는다
    assert not file_case.dir_exists(_path(file_case, _c7()))
    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.root, gone)
    assert kept_content == b"kept"
    assert file_case.dir_exists(f"{file_case.root.value}/license-contracts")


async def test_delete_folder_does_not_touch_a_deal_folder_with_the_same_files(
    file_case: FileStorageCase,
) -> None:
    """계약 폴더를 삭제해도 Deal 폴더의 파일은 그대로다."""
    # given: Deal 폴더와 계약 폴더에 저장된 파일
    deal = folder_of(
        "20261016-A001",
    )
    deal_file = await _put(file_case, deal, b"deal file")
    await _put(file_case, _c7())

    # when: 계약 폴더를 삭제한다 (전제: Fake·Local 공통)
    await file_case.storage.delete_folder(file_case.root, _c7())

    content = await _read(file_case, deal_file)

    # then: Deal 폴더의 파일은 읽힌다
    assert content == b"deal file"


async def test_delete_folder_of_a_missing_folder_passes_silently(
    file_case: FileStorageCase,
) -> None:
    """없는 폴더를 삭제해도 조용히 지나간다."""
    # given: 쓸 수 있는 빈 저장 루트
    await file_case.storage.check_writable(file_case.root)

    # when: 없는 폴더를 삭제한다 (전제: Fake·Local 공통)
    await file_case.storage.delete_folder(file_case.root, _c7())

    # then: 오류 없이 루트는 비어 있다
    assert file_case.entries(file_case.root.value) == []


async def test_delete_folder_twice_is_the_same_as_once(file_case: FileStorageCase) -> None:
    """폴더를 두 번 삭제해도 한 번과 같다."""
    # given: 이미 삭제한 폴더
    await _put(file_case, _c7())
    await file_case.storage.delete_folder(file_case.root, _c7())

    # when: 같은 폴더를 다시 삭제한다 (전제: Fake·Local 공통)
    await file_case.storage.delete_folder(file_case.root, _c7())

    # then: 오류 없이 폴더가 없는 상태 그대로다
    assert not file_case.dir_exists(_path(file_case, _c7()))


async def test_delete_folder_does_not_touch_another_root(file_case: FileStorageCase) -> None:
    """다른 저장 루트의 같은 폴더는 건드리지 않는다."""
    # given: 다른 저장 루트에 저장된 파일
    location = location_in(_c7(), uuid4().hex)
    await file_case.storage.save(file_case.other_root, location, BytesSource(b"x"), max_bytes=10)

    # when: 기본 루트의 같은 폴더를 삭제한다 (전제: Fake·Local 공통)
    await file_case.storage.delete_folder(file_case.root, _c7())

    # then: 다른 루트의 파일은 그대로다
    other = "/".join([file_case.other_root.value, *_c7().parts])
    assert file_case.entries(other) == [location.key]


@pytest.mark.parametrize("part", ["..", ".x", "a/b", "", "a" * 65, "a\x00b"])
async def test_save_rejects_a_folder_part_that_is_not_allowed(
    file_case: FileStorageCase, part: str
) -> None:
    """허용되지 않는 폴더 조각으로는 저장할 수 없다."""
    # given: 허용되지 않는 폴더 조각이 든 위치
    location = location_in(folder_of("license-contracts", part), uuid4().hex)

    # when·then: 저장하면 ValueError가 난다 (전제: Fake·Local 공통)
    with pytest.raises(ValueError):  # noqa: PT011
        await file_case.storage.save(file_case.root, location, BytesSource(b"x"), max_bytes=10)

    # then: 저장 루트에 아무것도 만들지 않았다
    assert not file_case.dir_exists(file_case.root.value)


@pytest.mark.parametrize("part", ["..", ".x", "a/b", "", "a" * 65, "a\x00b"])
async def test_open_and_delete_reject_a_folder_part_that_is_not_allowed(
    file_case: FileStorageCase, part: str
) -> None:
    """허용되지 않는 폴더 조각으로는 열기·삭제도 할 수 없다."""
    # given: 허용되지 않는 폴더 조각이 든 위치
    location = location_in(folder_of(part), uuid4().hex)

    # when·then: 열면 ValueError가 난다 (전제: Fake·Local 공통)
    # when·then: 삭제해도 ValueError가 난다
    with pytest.raises(ValueError):  # noqa: PT011
        await file_case.storage.open(file_case.root, location)
    with pytest.raises(ValueError):  # noqa: PT011
        await file_case.storage.delete(file_case.root, location)


@pytest.mark.parametrize("part", ["..", ".x", "a/b", "", "a" * 65, "a\x00b"])
async def test_delete_folder_rejects_a_folder_part_that_is_not_allowed(
    file_case: FileStorageCase, part: str
) -> None:
    """허용되지 않는 폴더 조각으로는 폴더를 삭제할 수 없다."""
    # given: 저장된 파일
    kept = await _put(file_case, _c7(), b"kept")

    # when·then: 허용되지 않는 조각으로 폴더를 삭제하면 ValueError가 난다 (전제: Fake·Local 공통)
    with pytest.raises(ValueError):  # noqa: PT011
        await file_case.storage.delete_folder(
            file_case.root,
            folder_of(
                part,
            ),
        )

    # then: 저장된 파일은 그대로 읽힌다
    content = await _read(file_case, kept)

    assert content == b"kept"
