"""FileStorage 삭제 계약: 파일 하나와 폴더(Deal 디렉터리) 삭제. Fake·Local 공통."""

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
    """delete는 파일을 지운다."""
    # given: 저장된 파일 하나
    location = await _put(file_case)

    # when: 파일을 삭제한다
    await file_case.storage.delete(file_case.root, location)

    # then: 열 수 없고 Deal 디렉터리에 항목이 없다
    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.root, location)
    assert file_case.entries(_deal_dir(file_case)) == []


async def test_delete_keeps_the_other_files_of_the_same_deal(file_case: FileStorageCase) -> None:
    """delete는 같은 Deal의 다른 파일을 남긴다."""
    # given: 같은 Deal의 파일 둘
    doomed = await _put(file_case, data=b"gone")
    kept = await _put(file_case, data=b"kept")

    # when: 한 파일을 삭제한다
    await file_case.storage.delete(file_case.root, doomed)

    # then: 다른 파일은 남아 내용을 읽을 수 있다
    assert file_case.entries(_deal_dir(file_case)) == [kept.key]
    opened = await file_case.storage.open(file_case.root, kept)
    assert b"".join([chunk async for chunk in opened.chunks]) == b"kept"


async def test_delete_of_a_missing_file_passes_silently(file_case: FileStorageCase) -> None:
    """없는 파일을 지워도 오류가 없다."""
    # given: 쓸 수 있는 저장 위치
    await file_case.storage.check_writable(file_case.root)

    # when·then: 없는 파일을 삭제해도 오류가 없다
    await file_case.storage.delete(file_case.root, deal_location(DEAL, uuid4().hex))


async def test_delete_when_the_root_does_not_exist_passes_silently(
    file_case: FileStorageCase,
) -> None:
    """저장 위치 루트가 없어도 delete는 오류 없이 지나가고 루트를 만들지 않는다."""
    # when: 루트가 없는 상태에서 파일을 삭제한다
    await file_case.storage.delete(file_case.root, deal_location(DEAL, uuid4().hex))

    # then: 루트 디렉터리가 생기지 않았다
    assert not file_case.dir_exists(file_case.root.value)


async def test_deleting_twice_is_the_same_as_deleting_once(file_case: FileStorageCase) -> None:
    """두 번 지워도 한 번 지운 것과 같다."""
    # given: 이미 삭제한 파일
    location = await _put(file_case)
    await file_case.storage.delete(file_case.root, location)

    # when: 같은 파일을 다시 삭제한다
    await file_case.storage.delete(file_case.root, location)

    # then: Deal 디렉터리에 항목이 없다
    assert file_case.entries(_deal_dir(file_case)) == []


# ---- delete_folder (Deal 폴더) ----


async def test_delete_folder_of_a_deal_removes_every_file_and_the_deal_directory(
    file_case: FileStorageCase,
) -> None:
    """폴더 삭제는 Deal의 모든 파일과 Deal 디렉터리를 지운다."""
    # given: 한 Deal의 파일 둘
    first = await _put(file_case)
    second = await _put(file_case)

    # when: Deal 폴더를 삭제한다
    await file_case.storage.delete_folder(file_case.root, deal_folder_of(DEAL))

    # then: Deal 디렉터리가 없고 두 파일 모두 열 수 없다
    assert not file_case.dir_exists(_deal_dir(file_case))
    for location in (first, second):
        with pytest.raises(StoredFileMissingError):
            await file_case.storage.open(file_case.root, location)


async def test_delete_folder_of_a_deal_keeps_the_files_of_other_deals(
    file_case: FileStorageCase,
) -> None:
    """폴더 삭제는 다른 Deal의 파일을 남긴다."""
    # given: 두 Deal의 파일
    await _put(file_case, DEAL)
    other = await _put(file_case, OTHER_DEAL, data=b"other deal")

    # when: 한 Deal의 폴더를 삭제한다
    await file_case.storage.delete_folder(file_case.root, deal_folder_of(DEAL))

    # then: 다른 Deal의 파일과 디렉터리가 남는다
    opened = await file_case.storage.open(file_case.root, other)
    assert b"".join([chunk async for chunk in opened.chunks]) == b"other deal"
    assert file_case.dir_exists(_deal_dir(file_case, OTHER_DEAL))


async def test_delete_folder_of_a_deal_keeps_the_root_directory(file_case: FileStorageCase) -> None:
    """폴더 삭제는 루트 디렉터리를 남긴다."""
    # given: Deal 파일 하나
    await _put(file_case)

    # when: Deal 폴더를 삭제한다
    await file_case.storage.delete_folder(file_case.root, deal_folder_of(DEAL))

    # then: 루트 디렉터리는 남는다
    assert file_case.dir_exists(file_case.root.value)


async def test_delete_folder_of_a_deal_of_a_deal_without_a_directory_passes_silently(
    file_case: FileStorageCase,
) -> None:
    """디렉터리가 없는 Deal의 폴더 삭제도 오류 없이 지나간다."""
    # given: 비어 있는 쓸 수 있는 저장 위치
    await file_case.storage.check_writable(file_case.root)

    # when: 디렉터리가 없는 Deal의 폴더를 삭제한다
    await file_case.storage.delete_folder(file_case.root, deal_folder_of(DEAL))

    # then: 루트는 여전히 비어 있다
    assert file_case.entries(file_case.root.value) == []


async def test_delete_folder_of_a_deal_when_the_root_does_not_exist_passes_silently(
    file_case: FileStorageCase,
) -> None:
    """루트가 없어도 폴더 삭제는 오류 없이 지나가고 루트를 만들지 않는다."""
    # when: 루트가 없는 상태에서 Deal 폴더를 삭제한다
    await file_case.storage.delete_folder(file_case.root, deal_folder_of(DEAL))

    # then: 루트 디렉터리가 생기지 않았다
    assert not file_case.dir_exists(file_case.root.value)


async def test_delete_folder_of_a_deal_does_not_touch_another_root(
    file_case: FileStorageCase,
) -> None:
    """폴더 삭제는 다른 루트의 같은 Deal 폴더를 건드리지 않는다."""
    # given: 다른 루트에 저장된 같은 Deal의 파일
    location = deal_location(DEAL, uuid4().hex)
    await file_case.storage.save(file_case.other_root, location, BytesSource(b"x"), max_bytes=10)

    # when: 기본 루트에서 그 Deal 폴더를 삭제한다
    await file_case.storage.delete_folder(file_case.root, deal_folder_of(DEAL))

    # then: 다른 루트의 파일은 그대로다
    assert file_case.entries(f"{file_case.other_root.value}/{DEAL.value}") == [location.key]
