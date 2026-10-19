"""FileStorage 계약(P2b AC-06·07): 쓰기 확인·저장·열기. FakeFileStorage와 LocalFileStorage 공통.

local은 tmp_path 아래 실제 디렉터리를 쓴다. 삭제 계약은 test_file_storage_delete_contract.py.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.ports.file_storage import (
    StorageNotWritableError,
    StoredFileLocation,
    StoredFileMissingError,
)
from app.domain.common.errors import InvalidValueError
from app.domain.deal.code import DealCode
from tests.fakes.file_storage import BytesSource

if TYPE_CHECKING:
    from app.application.ports.file_storage import OpenedFile
    from tests.unit.repositories.file_storage_case import FileStorageCase

DEAL = DealCode("20261016-A001")
MAX_BYTES = 100 * 1024 * 1024
TOO_LARGE = "파일 크기가 100MB를 초과합니다. (최대 100MB)"
MIB = 1024 * 1024


def _location(deal: DealCode = DEAL, key: str | None = None) -> StoredFileLocation:
    return StoredFileLocation(deal_code=deal, key=key or uuid4().hex)


async def _read_all(opened: OpenedFile) -> bytes:
    return b"".join([chunk async for chunk in opened.chunks])


# ---- check_writable ----


async def test_check_writable_creates_the_missing_directory_with_its_parents(
    file_case: FileStorageCase,
) -> None:
    assert not file_case.dir_exists(file_case.root.value)

    await file_case.storage.check_writable(file_case.root)

    assert file_case.dir_exists(file_case.root.value)


async def test_check_writable_leaves_no_file_behind(file_case: FileStorageCase) -> None:
    await file_case.storage.check_writable(file_case.root)

    assert file_case.entries(file_case.root.value) == []


async def test_check_writable_leaves_existing_files_untouched(file_case: FileStorageCase) -> None:
    location = _location()
    await file_case.storage.save(file_case.root, location, BytesSource(b"keep me"), max_bytes=100)
    before = file_case.entries(file_case.root.value)

    await file_case.storage.check_writable(file_case.root)

    assert file_case.entries(file_case.root.value) == before
    assert await _read_all(await file_case.storage.open(file_case.root, location)) == b"keep me"


async def test_check_writable_can_be_repeated(file_case: FileStorageCase) -> None:
    await file_case.storage.check_writable(file_case.root)

    await file_case.storage.check_writable(file_case.root)

    assert file_case.entries(file_case.root.value) == []


async def test_check_writable_on_an_unwritable_root_raises(file_case: FileStorageCase) -> None:
    with pytest.raises(StorageNotWritableError):
        await file_case.storage.check_writable(file_case.blocked_root)


# ---- save / open ----


async def test_save_then_open_returns_the_same_bytes_and_size(file_case: FileStorageCase) -> None:
    data = bytes(range(256)) * 4
    location = _location()

    written = await file_case.storage.save(
        file_case.root, location, BytesSource(data), max_bytes=MAX_BYTES
    )
    opened = await file_case.storage.open(file_case.root, location)

    assert written == len(data)
    assert opened.size == len(data)
    assert await _read_all(opened) == data


async def test_save_of_a_file_larger_than_one_chunk_keeps_every_byte(
    file_case: FileStorageCase,
) -> None:
    data = (b"0123456789abcdef" * (MIB // 16)) * 2 + b"tail"  # 2 MiB + 4 바이트
    location = _location()

    written = await file_case.storage.save(
        file_case.root, location, BytesSource(data), max_bytes=MAX_BYTES
    )

    assert written == len(data)
    assert await _read_all(await file_case.storage.open(file_case.root, location)) == data


async def test_save_of_an_empty_file_is_allowed(file_case: FileStorageCase) -> None:
    location = _location()

    written = await file_case.storage.save(
        file_case.root, location, BytesSource(b""), max_bytes=MAX_BYTES
    )
    opened = await file_case.storage.open(file_case.root, location)

    assert written == 0
    assert opened.size == 0
    assert await _read_all(opened) == b""


async def test_save_accepts_exactly_the_maximum_size(file_case: FileStorageCase) -> None:
    data = b"x" * 1024

    written = await file_case.storage.save(
        file_case.root, _location(), BytesSource(data), max_bytes=1024
    )

    assert written == 1024


async def test_save_of_one_byte_over_the_limit_raises_the_file_too_large_error(
    file_case: FileStorageCase,
) -> None:
    with pytest.raises(InvalidValueError) as caught:
        await file_case.storage.save(
            file_case.root, _location(), BytesSource(b"x" * 1025), max_bytes=1024
        )

    assert str(caught.value) == TOO_LARGE


async def test_save_over_the_limit_leaves_no_file_and_nothing_to_open(
    file_case: FileStorageCase,
) -> None:
    location = _location()
    with pytest.raises(InvalidValueError):
        await file_case.storage.save(
            file_case.root, location, BytesSource(b"x" * 5000), max_bytes=1024
        )

    assert file_case.entries(f"{file_case.root.value}/{DEAL.value}") == []
    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.root, location)


async def test_save_with_an_existing_key_raises_and_keeps_the_first_content(
    file_case: FileStorageCase,
) -> None:
    location = _location()
    await file_case.storage.save(file_case.root, location, BytesSource(b"first"), max_bytes=100)

    with pytest.raises(StorageNotWritableError):
        await file_case.storage.save(
            file_case.root, location, BytesSource(b"second"), max_bytes=100
        )

    assert await _read_all(await file_case.storage.open(file_case.root, location)) == b"first"


async def test_save_into_an_unwritable_root_raises(file_case: FileStorageCase) -> None:
    with pytest.raises(StorageNotWritableError):
        await file_case.storage.save(
            file_case.blocked_root, _location(), BytesSource(b"data"), max_bytes=100
        )


async def test_save_creates_the_deal_directory_when_it_is_missing(
    file_case: FileStorageCase,
) -> None:
    location = _location()
    await file_case.storage.save(file_case.root, location, BytesSource(b"data"), max_bytes=100)

    assert file_case.entries(f"{file_case.root.value}/{DEAL.value}") == [location.key]


async def test_files_of_different_deals_do_not_collide_on_the_same_key(
    file_case: FileStorageCase,
) -> None:
    other_deal = DealCode("20261016-B002")
    key = uuid4().hex
    await file_case.storage.save(
        file_case.root, _location(DEAL, key), BytesSource(b"first deal"), max_bytes=100
    )
    await file_case.storage.save(
        file_case.root, _location(other_deal, key), BytesSource(b"second deal"), max_bytes=100
    )

    first = await file_case.storage.open(file_case.root, _location(DEAL, key))
    second = await file_case.storage.open(file_case.root, _location(other_deal, key))

    assert (await _read_all(first), await _read_all(second)) == (b"first deal", b"second deal")


async def test_files_under_different_roots_are_independent(file_case: FileStorageCase) -> None:
    location = _location()
    await file_case.storage.save(file_case.root, location, BytesSource(b"here"), max_bytes=100)

    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.other_root, location)


async def test_open_of_an_unknown_key_raises_missing(file_case: FileStorageCase) -> None:
    await file_case.storage.check_writable(file_case.root)

    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.root, _location())


async def test_open_when_the_root_does_not_exist_raises_missing(
    file_case: FileStorageCase,
) -> None:
    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.root, _location())


# ---- 경로 조작 방어 ----

BAD_KEYS = ["../escape", "a/b", "", ".", "..", "x\x00y", "/absolute", "..%2f"]


@pytest.mark.parametrize("key", BAD_KEYS)
async def test_save_rejects_a_key_that_is_not_a_plain_file_name(
    file_case: FileStorageCase, key: str
) -> None:
    with pytest.raises(ValueError):  # noqa: PT011 - 키 형식 위반은 ValueError 계열이면 된다
        await file_case.storage.save(
            file_case.root,
            StoredFileLocation(deal_code=DEAL, key=key),
            BytesSource(b"x"),
            max_bytes=10,
        )

    assert not file_case.dir_exists(f"{file_case.root.value}/{DEAL.value}")


@pytest.mark.parametrize("key", BAD_KEYS)
async def test_open_rejects_a_key_that_is_not_a_plain_file_name(
    file_case: FileStorageCase, key: str
) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        await file_case.storage.open(file_case.root, StoredFileLocation(deal_code=DEAL, key=key))


@pytest.mark.parametrize("key", BAD_KEYS)
async def test_delete_rejects_a_key_that_is_not_a_plain_file_name(
    file_case: FileStorageCase, key: str
) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        await file_case.storage.delete(file_case.root, StoredFileLocation(deal_code=DEAL, key=key))
