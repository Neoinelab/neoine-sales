"""FileStorage 계약: 쓰기 확인·저장·열기. FakeFileStorage와 LocalFileStorage 공통.

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
from tests.fakes.file_storage import BytesSource, deal_location

if TYPE_CHECKING:
    from app.application.ports.file_storage import OpenedFile
    from tests.unit.repositories.file_storage_case import FileStorageCase

DEAL = DealCode("20261016-A001")
MAX_BYTES = 100 * 1024 * 1024
TOO_LARGE = "파일 크기가 100MB를 초과합니다. (최대 100MB)"
MIB = 1024 * 1024


def _location(deal: DealCode = DEAL, key: str | None = None) -> StoredFileLocation:
    return deal_location(deal, key or uuid4().hex)


async def _read_all(opened: OpenedFile) -> bytes:
    return b"".join([chunk async for chunk in opened.chunks])


# ---- check_writable ----


async def test_check_writable_creates_the_missing_directory_with_its_parents(
    file_case: FileStorageCase,
) -> None:
    """쓰기 확인은 없는 디렉터리를 상위까지 만든다."""
    # given: 존재하지 않는 저장 루트
    assert not file_case.dir_exists(file_case.root.value)

    # when: 쓰기 확인을 한다
    await file_case.storage.check_writable(file_case.root)

    # then: 루트가 만들어졌다
    assert file_case.dir_exists(file_case.root.value)


async def test_check_writable_leaves_no_file_behind(file_case: FileStorageCase) -> None:
    """쓰기 확인은 파일을 남기지 않는다."""
    # when: 쓰기 확인을 한다 (전제: 비어 있는 저장 루트)
    await file_case.storage.check_writable(file_case.root)

    # then: 루트에 항목이 없다
    assert file_case.entries(file_case.root.value) == []


async def test_check_writable_leaves_existing_files_untouched(file_case: FileStorageCase) -> None:
    """쓰기 확인은 기존 파일을 건드리지 않는다."""
    # given: 파일 하나가 저장되어 있다
    location = _location()
    await file_case.storage.save(file_case.root, location, BytesSource(b"keep me"), max_bytes=100)
    before = file_case.entries(file_case.root.value)

    # when: 쓰기 확인을 한다
    await file_case.storage.check_writable(file_case.root)

    # then: 항목과 내용이 그대로다
    assert file_case.entries(file_case.root.value) == before
    assert await _read_all(await file_case.storage.open(file_case.root, location)) == b"keep me"


async def test_check_writable_can_be_repeated(file_case: FileStorageCase) -> None:
    """쓰기 확인은 반복해도 된다."""
    # given: 한 번 확인한 저장 루트
    await file_case.storage.check_writable(file_case.root)

    # when: 다시 확인한다
    await file_case.storage.check_writable(file_case.root)

    # then: 루트에 항목이 없다
    assert file_case.entries(file_case.root.value) == []


async def test_check_writable_on_an_unwritable_root_raises(file_case: FileStorageCase) -> None:
    """쓸 수 없는 루트는 쓰기 확인에서 오류다."""
    # when·then: 쓸 수 없는 루트를 확인하면 쓰기 불가 오류다
    with pytest.raises(StorageNotWritableError):
        await file_case.storage.check_writable(file_case.blocked_root)


# ---- save / open ----


async def test_save_then_open_returns_the_same_bytes_and_size(file_case: FileStorageCase) -> None:
    """저장한 뒤 열면 같은 바이트와 크기를 돌려준다."""
    # given: 바이트 데이터와 새 위치
    data = bytes(range(256)) * 4
    location = _location()

    # when: 저장하고 연다
    written = await file_case.storage.save(
        file_case.root, location, BytesSource(data), max_bytes=MAX_BYTES
    )
    opened = await file_case.storage.open(file_case.root, location)

    # then: 쓴 크기·열린 크기·내용이 데이터와 같다
    assert written == len(data)
    assert opened.size == len(data)
    assert await _read_all(opened) == data


async def test_save_of_a_file_larger_than_one_chunk_keeps_every_byte(
    file_case: FileStorageCase,
) -> None:
    """한 청크보다 큰 파일도 모든 바이트가 보존된다."""
    # given: 2MiB+4바이트 데이터
    data = (b"0123456789abcdef" * (MIB // 16)) * 2 + b"tail"  # 2 MiB + 4 바이트
    location = _location()

    # when: 저장한다
    written = await file_case.storage.save(
        file_case.root, location, BytesSource(data), max_bytes=MAX_BYTES
    )

    # then: 쓴 크기와 읽은 내용이 같다
    assert written == len(data)
    assert await _read_all(await file_case.storage.open(file_case.root, location)) == data


async def test_save_of_an_empty_file_is_allowed(file_case: FileStorageCase) -> None:
    """빈 파일도 저장할 수 있다."""
    # given: 새 위치
    location = _location()

    # when: 빈 내용을 저장하고 연다
    written = await file_case.storage.save(
        file_case.root, location, BytesSource(b""), max_bytes=MAX_BYTES
    )
    opened = await file_case.storage.open(file_case.root, location)

    # then: 크기 0, 내용이 비어 있다
    assert written == 0
    assert opened.size == 0
    assert await _read_all(opened) == b""


async def test_save_accepts_exactly_the_maximum_size(file_case: FileStorageCase) -> None:
    """정확히 한도 크기는 저장된다."""
    # given: 한도와 같은 크기의 데이터
    data = b"x" * 1024

    # when: 저장한다
    written = await file_case.storage.save(
        file_case.root, _location(), BytesSource(data), max_bytes=1024
    )

    # then: 쓴 크기가 한도다
    assert written == 1024


async def test_save_of_one_byte_over_the_limit_raises_the_file_too_large_error(
    file_case: FileStorageCase,
) -> None:
    """한도보다 1바이트 큰 내용은 크기 초과 오류다."""
    # when·then: 한도+1바이트를 저장하면 크기 초과 오류다
    with pytest.raises(InvalidValueError) as caught:
        await file_case.storage.save(
            file_case.root, _location(), BytesSource(b"x" * 1025), max_bytes=1024
        )

    # then: 문구는 100MB 초과 문구다
    assert str(caught.value) == TOO_LARGE


async def test_save_over_the_limit_leaves_no_file_and_nothing_to_open(
    file_case: FileStorageCase,
) -> None:
    """한도 초과 저장은 파일을 남기지 않는다."""
    # given: 새 위치
    location = _location()
    # when: 한도를 크게 넘는 내용을 저장한다
    with pytest.raises(InvalidValueError):
        await file_case.storage.save(
            file_case.root, location, BytesSource(b"x" * 5000), max_bytes=1024
        )

    # then: Deal 폴더가 비어 있고 열 수도 없다
    assert file_case.entries(f"{file_case.root.value}/{DEAL.value}") == []
    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.root, location)


async def test_save_with_an_existing_key_raises_and_keeps_the_first_content(
    file_case: FileStorageCase,
) -> None:
    """이미 있는 키로 저장하면 오류이고 처음 내용이 남는다"""
    # given: 저장된 키
    location = _location()
    await file_case.storage.save(file_case.root, location, BytesSource(b"first"), max_bytes=100)

    # when·then: 같은 키로 다시 저장하면 쓰기 불가 오류다
    with pytest.raises(StorageNotWritableError):
        await file_case.storage.save(
            file_case.root, location, BytesSource(b"second"), max_bytes=100
        )

    # then: 처음 내용이 그대로다
    assert await _read_all(await file_case.storage.open(file_case.root, location)) == b"first"


async def test_save_into_an_unwritable_root_raises(file_case: FileStorageCase) -> None:
    """쓸 수 없는 루트에 저장하면 오류다."""
    # when·then: 쓸 수 없는 루트에 저장하면 쓰기 불가 오류다
    with pytest.raises(StorageNotWritableError):
        await file_case.storage.save(
            file_case.blocked_root, _location(), BytesSource(b"data"), max_bytes=100
        )


async def test_save_creates_the_deal_directory_when_it_is_missing(
    file_case: FileStorageCase,
) -> None:
    """저장은 없는 Deal 폴더를 만든다."""
    # given: 새 위치
    location = _location()
    # when: 저장한다
    await file_case.storage.save(file_case.root, location, BytesSource(b"data"), max_bytes=100)

    # then: Deal 폴더에 그 키 파일 하나가 있다
    assert file_case.entries(f"{file_case.root.value}/{DEAL.value}") == [location.key]


async def test_files_of_different_deals_do_not_collide_on_the_same_key(
    file_case: FileStorageCase,
) -> None:
    """다른 Deal의 같은 키 파일은 서로 섞이지 않는다."""
    # given: 두 Deal에 같은 키로 서로 다른 내용을 저장한다
    other_deal = DealCode("20261016-B002")
    key = uuid4().hex
    await file_case.storage.save(
        file_case.root, _location(DEAL, key), BytesSource(b"first deal"), max_bytes=100
    )
    await file_case.storage.save(
        file_case.root, _location(other_deal, key), BytesSource(b"second deal"), max_bytes=100
    )

    # when: 두 파일을 연다
    first = await file_case.storage.open(file_case.root, _location(DEAL, key))
    second = await file_case.storage.open(file_case.root, _location(other_deal, key))

    # then: 각각 자기 내용이다
    assert (await _read_all(first), await _read_all(second)) == (b"first deal", b"second deal")


async def test_files_under_different_roots_are_independent(file_case: FileStorageCase) -> None:
    """다른 루트의 파일은 서로 독립이다."""
    # given: 한 루트에 저장한 파일
    location = _location()
    await file_case.storage.save(file_case.root, location, BytesSource(b"here"), max_bytes=100)

    # when·then: 다른 루트에서 열면 파일 없음 오류다
    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.other_root, location)


async def test_open_of_an_unknown_key_raises_missing(file_case: FileStorageCase) -> None:
    """없는 키를 열면 파일 없음 오류다."""
    # given: 존재하는 빈 루트
    await file_case.storage.check_writable(file_case.root)

    # when·then: 없는 키를 열면 파일 없음 오류다
    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.root, _location())


async def test_open_when_the_root_does_not_exist_raises_missing(
    file_case: FileStorageCase,
) -> None:
    """루트가 없어도 열면 파일 없음 오류다."""
    # when·then: 없는 루트에서 열면 파일 없음 오류다
    with pytest.raises(StoredFileMissingError):
        await file_case.storage.open(file_case.root, _location())


# ---- 경로 조작 방어 ----

BAD_KEYS = ["../escape", "a/b", "", ".", "..", "x\x00y", "/absolute", "..%2f"]


@pytest.mark.parametrize("key", BAD_KEYS)
async def test_save_rejects_a_key_that_is_not_a_plain_file_name(
    file_case: FileStorageCase, key: str
) -> None:
    """단순 파일 이름이 아닌 키로는 저장할 수 없다."""
    # when·then: 경로 조작 키로 저장하면 오류다
    with pytest.raises(ValueError):  # noqa: PT011 - 키 형식 위반은 ValueError 계열이면 된다
        await file_case.storage.save(
            file_case.root,
            deal_location(DEAL, key),
            BytesSource(b"x"),
            max_bytes=10,
        )

    # then: Deal 폴더가 만들어지지 않는다
    assert not file_case.dir_exists(f"{file_case.root.value}/{DEAL.value}")


@pytest.mark.parametrize("key", BAD_KEYS)
async def test_open_rejects_a_key_that_is_not_a_plain_file_name(
    file_case: FileStorageCase, key: str
) -> None:
    """단순 파일 이름이 아닌 키로는 열 수 없다."""
    # when·then: 경로 조작 키로 열면 오류다
    with pytest.raises(ValueError):  # noqa: PT011
        await file_case.storage.open(file_case.root, deal_location(DEAL, key))


@pytest.mark.parametrize("key", BAD_KEYS)
async def test_delete_rejects_a_key_that_is_not_a_plain_file_name(
    file_case: FileStorageCase, key: str
) -> None:
    """단순 파일 이름이 아닌 키로는 지울 수 없다."""
    # when·then: 경로 조작 키로 지우면 오류다
    with pytest.raises(ValueError):  # noqa: PT011
        await file_case.storage.delete(file_case.root, deal_location(DEAL, key))
