"""FileStorage 폴더 계약(AC32·AC33·AC36): 중첩 폴더 저장·열기·삭제와 조각 검증. Fake·Local 공통.

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
    location = await _put(file_case, _c7(), b"nested")

    assert await _read(file_case, location) == b"nested"
    assert file_case.entries(_path(file_case, _c7())) == [location.key]
    assert file_case.entries(f"{file_case.root.value}/license-contracts") == ["7"]


async def test_the_same_key_in_different_folders_is_a_different_file(
    file_case: FileStorageCase,
) -> None:
    key = uuid4().hex
    first = location_in(_c7(), key)
    second = location_in(_c8(), key)

    await file_case.storage.save(file_case.root, first, BytesSource(b"one"), max_bytes=10)
    await file_case.storage.save(file_case.root, second, BytesSource(b"two"), max_bytes=10)

    assert await _read(file_case, first) == b"one"
    assert await _read(file_case, second) == b"two"


async def test_open_in_another_folder_is_missing(file_case: FileStorageCase) -> None:
    location = await _put(file_case, _c7())

    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.root, location_in(_c8(), location.key))


async def test_delete_of_a_file_keeps_the_nested_folder(file_case: FileStorageCase) -> None:
    location = await _put(file_case, _c7())

    await file_case.storage.delete(file_case.root, location)

    assert file_case.dir_exists(_path(file_case, _c7()))
    assert file_case.entries(_path(file_case, _c7())) == []


async def test_delete_folder_removes_the_tree_and_keeps_sibling_folders(
    file_case: FileStorageCase,
) -> None:
    gone = await _put(file_case, _c7())
    kept = await _put(file_case, _c8(), b"kept")

    await file_case.storage.delete_folder(file_case.root, _c7())

    assert not file_case.dir_exists(_path(file_case, _c7()))
    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.root, gone)
    assert await _read(file_case, kept) == b"kept"
    assert file_case.dir_exists(f"{file_case.root.value}/license-contracts")


async def test_delete_folder_does_not_touch_a_deal_folder_with_the_same_files(
    file_case: FileStorageCase,
) -> None:
    deal = folder_of(
        "20261016-A001",
    )
    deal_file = await _put(file_case, deal, b"deal file")
    await _put(file_case, _c7())

    await file_case.storage.delete_folder(file_case.root, _c7())

    assert await _read(file_case, deal_file) == b"deal file"


async def test_delete_folder_of_a_missing_folder_passes_silently(
    file_case: FileStorageCase,
) -> None:
    await file_case.storage.check_writable(file_case.root)

    await file_case.storage.delete_folder(file_case.root, _c7())

    assert file_case.entries(file_case.root.value) == []


async def test_delete_folder_twice_is_the_same_as_once(file_case: FileStorageCase) -> None:
    await _put(file_case, _c7())
    await file_case.storage.delete_folder(file_case.root, _c7())

    await file_case.storage.delete_folder(file_case.root, _c7())

    assert not file_case.dir_exists(_path(file_case, _c7()))


async def test_delete_folder_does_not_touch_another_root(file_case: FileStorageCase) -> None:
    location = location_in(_c7(), uuid4().hex)
    await file_case.storage.save(file_case.other_root, location, BytesSource(b"x"), max_bytes=10)

    await file_case.storage.delete_folder(file_case.root, _c7())

    other = "/".join([file_case.other_root.value, *_c7().parts])
    assert file_case.entries(other) == [location.key]


@pytest.mark.parametrize("part", ["..", ".x", "a/b", "", "a" * 65, "a\x00b"])
async def test_save_rejects_a_folder_part_that_is_not_allowed(
    file_case: FileStorageCase, part: str
) -> None:
    location = location_in(folder_of("license-contracts", part), uuid4().hex)

    with pytest.raises(ValueError):  # noqa: PT011
        await file_case.storage.save(file_case.root, location, BytesSource(b"x"), max_bytes=10)

    assert not file_case.dir_exists(file_case.root.value)


@pytest.mark.parametrize("part", ["..", ".x", "a/b", "", "a" * 65, "a\x00b"])
async def test_open_and_delete_reject_a_folder_part_that_is_not_allowed(
    file_case: FileStorageCase, part: str
) -> None:
    location = location_in(folder_of(part), uuid4().hex)

    with pytest.raises(ValueError):  # noqa: PT011
        await file_case.storage.open(file_case.root, location)
    with pytest.raises(ValueError):  # noqa: PT011
        await file_case.storage.delete(file_case.root, location)


@pytest.mark.parametrize("part", ["..", ".x", "a/b", "", "a" * 65, "a\x00b"])
async def test_delete_folder_rejects_a_folder_part_that_is_not_allowed(
    file_case: FileStorageCase, part: str
) -> None:
    kept = await _put(file_case, _c7(), b"kept")

    with pytest.raises(ValueError):  # noqa: PT011
        await file_case.storage.delete_folder(
            file_case.root,
            folder_of(
                part,
            ),
        )

    assert await _read(file_case, kept) == b"kept"
