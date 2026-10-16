"""FileStorage.save 실패 정리 계약(P2b R1 리뷰 Minor 3): 읽다가 실패하면 부분 파일을 남기지 않는다.

같은 테스트가 FakeFileStorage와 LocalFileStorage(tmp_path)에서 돈다. 한도 초과는
test_file_storage_contract.py가 맡고, 여기서는 원본(source) 읽기 실패를 본다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.ports.file_storage import StoredFileLocation, StoredFileMissingError
from app.domain.deal.code import DealCode
from tests.fakes.file_storage import BytesSource
from tests.fakes.sources import ClientGone, FailingSource

if TYPE_CHECKING:
    from tests.unit.repositories.file_storage_case import FileStorageCase

DEAL = DealCode("20261016-A001")


def _location() -> StoredFileLocation:
    return StoredFileLocation(deal_code=DEAL, key=uuid4().hex)


async def test_a_source_that_fails_midway_surfaces_its_error_and_stores_nothing(
    file_case: FileStorageCase,
) -> None:
    location = _location()

    with pytest.raises(ClientGone):
        await file_case.storage.save(
            file_case.root,
            location,
            FailingSource(ClientGone(), good_chunks=2),
            max_bytes=1_000_000,
        )

    assert location.key not in file_case.entries(f"{file_case.root.value}/{DEAL.value}")
    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.root, location)


async def test_the_key_of_a_failed_save_can_be_used_again(file_case: FileStorageCase) -> None:
    location = _location()
    with pytest.raises(ClientGone):
        await file_case.storage.save(
            file_case.root, location, FailingSource(ClientGone()), max_bytes=1_000_000
        )

    saved = await file_case.storage.save(
        file_case.root, location, BytesSource(b"second try"), max_bytes=1_000
    )

    opened = await file_case.storage.open(file_case.root, location)
    assert saved == opened.size == len(b"second try")
