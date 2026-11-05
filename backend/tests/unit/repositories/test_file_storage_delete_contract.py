"""FileStorage 삭제 계약(P2b AC-14·15): 파일 하나와 폴더(Deal 디렉터리) 삭제. Fake·Local 공통."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.ports.file_storage import StoredFileLocation, StoredFileMissingError
from app.domain.deal.code import DealCode
from tests.fakes.file_storage import BytesSource, deal_folder_of, deal_location

if TYPE_CHECKING:
    from tests.unit.repositories.file_storage_case import FileStorageCase

DEAL = DealCode("20261016-A001")
OTHER_DEAL = DealCode("20261016-B002")


async def _put(
    case: FileStorageCase, deal: DealCode = DEAL, data: bytes = b"data"
) -> StoredFileLocation:
    location = deal_location(deal, uuid4().hex)
    await case.storage.save(case.root, location, BytesSource(data), max_bytes=1000)
    return location


def _deal_dir(case: FileStorageCase, deal: DealCode = DEAL) -> str:
    return f"{case.root.value}/{deal.value}"


# ---- delete ----


async def test_delete_removes_the_file(file_case: FileStorageCase) -> None:
    location = await _put(file_case)

    await file_case.storage.delete(file_case.root, location)

    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.root, location)
    assert file_case.entries(_deal_dir(file_case)) == []


async def test_delete_keeps_the_other_files_of_the_same_deal(file_case: FileStorageCase) -> None:
    doomed = await _put(file_case, data=b"gone")
    kept = await _put(file_case, data=b"kept")

    await file_case.storage.delete(file_case.root, doomed)

    assert file_case.entries(_deal_dir(file_case)) == [kept.key]
    opened = await file_case.storage.open(file_case.root, kept)
    assert b"".join([chunk async for chunk in opened.chunks]) == b"kept"


async def test_delete_of_a_missing_file_passes_silently(file_case: FileStorageCase) -> None:
    await file_case.storage.check_writable(file_case.root)

    await file_case.storage.delete(file_case.root, deal_location(DEAL, uuid4().hex))


async def test_delete_when_the_root_does_not_exist_passes_silently(
    file_case: FileStorageCase,
) -> None:
    await file_case.storage.delete(file_case.root, deal_location(DEAL, uuid4().hex))

    assert not file_case.dir_exists(file_case.root.value)


async def test_deleting_twice_is_the_same_as_deleting_once(file_case: FileStorageCase) -> None:
    location = await _put(file_case)
    await file_case.storage.delete(file_case.root, location)

    await file_case.storage.delete(file_case.root, location)

    assert file_case.entries(_deal_dir(file_case)) == []


# ---- delete_folder (Deal 폴더) ----


async def test_delete_folder_of_a_deal_removes_every_file_and_the_deal_directory(
    file_case: FileStorageCase,
) -> None:
    first = await _put(file_case)
    second = await _put(file_case)

    await file_case.storage.delete_folder(file_case.root, deal_folder_of(DEAL))

    assert not file_case.dir_exists(_deal_dir(file_case))
    for location in (first, second):
        with pytest.raises(StoredFileMissingError):
            await file_case.storage.open(file_case.root, location)


async def test_delete_folder_of_a_deal_keeps_the_files_of_other_deals(
    file_case: FileStorageCase,
) -> None:
    await _put(file_case, DEAL)
    other = await _put(file_case, OTHER_DEAL, data=b"other deal")

    await file_case.storage.delete_folder(file_case.root, deal_folder_of(DEAL))

    opened = await file_case.storage.open(file_case.root, other)
    assert b"".join([chunk async for chunk in opened.chunks]) == b"other deal"
    assert file_case.dir_exists(_deal_dir(file_case, OTHER_DEAL))


async def test_delete_folder_of_a_deal_keeps_the_root_directory(file_case: FileStorageCase) -> None:
    await _put(file_case)

    await file_case.storage.delete_folder(file_case.root, deal_folder_of(DEAL))

    assert file_case.dir_exists(file_case.root.value)


async def test_delete_folder_of_a_deal_of_a_deal_without_a_directory_passes_silently(
    file_case: FileStorageCase,
) -> None:
    await file_case.storage.check_writable(file_case.root)

    await file_case.storage.delete_folder(file_case.root, deal_folder_of(DEAL))

    assert file_case.entries(file_case.root.value) == []


async def test_delete_folder_of_a_deal_when_the_root_does_not_exist_passes_silently(
    file_case: FileStorageCase,
) -> None:
    await file_case.storage.delete_folder(file_case.root, deal_folder_of(DEAL))

    assert not file_case.dir_exists(file_case.root.value)


async def test_delete_folder_of_a_deal_does_not_touch_another_root(
    file_case: FileStorageCase,
) -> None:
    location = deal_location(DEAL, uuid4().hex)
    await file_case.storage.save(file_case.other_root, location, BytesSource(b"x"), max_bytes=10)

    await file_case.storage.delete_folder(file_case.root, deal_folder_of(DEAL))

    assert file_case.entries(f"{file_case.other_root.value}/{DEAL.value}") == [location.key]
