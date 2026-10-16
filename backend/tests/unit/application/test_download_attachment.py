"""DownloadAttachment(P2b AC-13, R1 리뷰 Minor 2): 메타데이터와 내용 스트림, 오류 구분.

읽기 권한 오류는 "파일 없음"(404)이 아니라 "저장 위치 사용 불가"(503)로 구분된다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from app.domain.attachment.errors import AttachmentContentMissingError, AttachmentNotFoundError

from app.application.ports.file_storage import StorageNotReadableError, StoredFileLocation
from app.application.storage.errors import DOWNLOAD_UNAVAILABLE, StorageUnavailableError
from app.domain.attachment.values import AttachmentId
from tests.support.expect import raises_with
from tests.unit.application.attachment_env import CONTENT_MISSING, KIM, NOT_FOUND

if TYPE_CHECKING:
    from app.application.ports.file_storage import OpenedFile
    from tests.unit.application.attachment_env import AttachmentEnv


async def _read_all(opened: OpenedFile) -> bytes:
    return b"".join([chunk async for chunk in opened.chunks])


async def test_download_returns_the_metadata_and_the_stored_bytes(
    attachment_env: AttachmentEnv,
) -> None:
    uploaded = await attachment_env.uploaded(KIM, "견적서.pdf", b"binary \x00\xff bytes")

    attachment, opened = await attachment_env.download.execute(uploaded.id)

    assert attachment.id == uploaded.id
    assert attachment.file_name.value == "견적서.pdf"
    assert opened.size == len(b"binary \x00\xff bytes")
    assert await _read_all(opened) == b"binary \x00\xff bytes"


async def test_download_of_an_empty_file_has_size_zero(attachment_env: AttachmentEnv) -> None:
    uploaded = await attachment_env.uploaded(KIM, "empty.txt", b"")

    _, opened = await attachment_env.download.execute(uploaded.id)

    assert (opened.size, await _read_all(opened)) == (0, b"")


async def test_download_of_an_unknown_id_is_not_found(attachment_env: AttachmentEnv) -> None:
    with raises_with(AttachmentNotFoundError, NOT_FOUND):
        await attachment_env.download.execute(AttachmentId(uuid4()))


async def test_a_row_without_its_disk_file_reports_the_content_as_missing(
    attachment_env: AttachmentEnv,
) -> None:
    uploaded = await attachment_env.uploaded(KIM, "a.pdf")
    await attachment_env.storage.delete(
        attachment_env.root,
        StoredFileLocation(deal_code=uploaded.deal_code, key=uploaded.storage_key),
    )

    with raises_with(AttachmentContentMissingError, CONTENT_MISSING):
        await attachment_env.download.execute(uploaded.id)


async def test_without_a_storage_location_the_download_is_unavailable(
    attachment_env: AttachmentEnv,
) -> None:
    uploaded = await attachment_env.uploaded(KIM, "a.pdf")
    await attachment_env.remove_storage_settings()

    with raises_with(StorageUnavailableError, DOWNLOAD_UNAVAILABLE):
        await attachment_env.download.execute(uploaded.id)


async def test_a_file_that_exists_but_cannot_be_read_is_unavailable_not_missing(
    attachment_env: AttachmentEnv,
) -> None:
    uploaded = await attachment_env.uploaded(KIM, "a.pdf")
    attachment_env.storage.fail_reads = True

    with raises_with(StorageUnavailableError, DOWNLOAD_UNAVAILABLE):
        await attachment_env.download.execute(uploaded.id)


async def test_the_file_is_looked_up_under_the_current_storage_location(
    attachment_env: AttachmentEnv,
) -> None:
    from app.domain.storage.path import StoragePath  # noqa: PLC0415

    uploaded = await attachment_env.uploaded(KIM, "a.pdf")
    async with attachment_env.env.uow_factory() as uow:
        await uow.storage_settings.save(
            StoragePath.parse("/data/moved"), updated_by=None, now=attachment_env.env.clock.now()
        )
        await uow.commit()

    with pytest.raises(AttachmentContentMissingError):
        await attachment_env.download.execute(uploaded.id)


def test_a_read_failure_is_a_different_error_from_a_missing_file() -> None:
    from app.application.ports.file_storage import StoredFileMissingError  # noqa: PLC0415

    assert not issubclass(StorageNotReadableError, StoredFileMissingError)
    assert not issubclass(StoredFileMissingError, StorageNotReadableError)
