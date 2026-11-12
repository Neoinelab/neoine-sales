"""DownloadAttachment: 메타데이터와 내용 스트림, 오류 구분.

읽기 권한 오류는 "파일 없음"(404)이 아니라 "저장 위치 사용 불가"(503)로 구분된다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.file_storage import StorageNotReadableError
from app.application.storage.errors import DOWNLOAD_UNAVAILABLE, StorageUnavailableError
from app.domain.attachment.errors import AttachmentContentMissingError, AttachmentNotFoundError
from app.domain.attachment.values import AttachmentId
from tests.fakes.file_storage import deal_location
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.attachment_env import CONTENT_MISSING, KIM, NOT_FOUND

if TYPE_CHECKING:
    from app.application.ports.file_storage import OpenedFile
    from tests.unit.application.attachment_env import AttachmentEnv


async def _read_all(opened: OpenedFile) -> bytes:
    return b"".join([chunk async for chunk in opened.chunks])


async def test_download_returns_the_metadata_and_the_stored_bytes(
    attachment_env: AttachmentEnv,
) -> None:
    """다운로드는 메타데이터와 저장한 바이트를 그대로 돌려준다.

    테스트 코드: AT-030
    """
    # given: 바이너리 내용의 "견적서.pdf"
    uploaded = await attachment_env.uploaded(KIM, "견적서.pdf", b"binary \x00\xff bytes")

    # when: 내려받는다
    attachment, opened = await attachment_env.download.execute(uploaded.id)

    # then: 메타데이터와 크기가 같고 읽은 바이트가 저장한 바이트와 같다
    assert attachment.id == uploaded.id
    assert attachment.file_name.value == "견적서.pdf"
    assert opened.size == len(b"binary \x00\xff bytes")
    assert await _read_all(opened) == b"binary \x00\xff bytes"


async def test_download_of_an_empty_file_has_size_zero(attachment_env: AttachmentEnv) -> None:
    """0바이트 파일은 크기 0과 빈 내용으로 내려간다.

    테스트 코드: AT-032
    """
    # given: 0바이트 "empty.txt"
    uploaded = await attachment_env.uploaded(KIM, "empty.txt", b"")

    # when: 내려받는다
    _, opened = await attachment_env.download.execute(uploaded.id)

    # then: 크기 0, 내용 빈 바이트다
    assert (opened.size, await _read_all(opened)) == (0, b"")


async def test_download_of_an_unknown_id_is_not_found(attachment_env: AttachmentEnv) -> None:
    """없는 id의 다운로드는 첨부 없음 오류다.

    테스트 코드: AT-033
    """
    # when·then: 없는 id를 내려받으면 첨부 없음 오류다 (전제: 저장 위치가 설정된 Deal)
    with raises_with(AttachmentNotFoundError, NOT_FOUND):
        await attachment_env.download.execute(AttachmentId(new_id()))


async def test_a_row_without_its_disk_file_reports_the_content_as_missing(
    attachment_env: AttachmentEnv,
) -> None:
    """디스크 파일이 없으면 내용 없음 오류다.

    테스트 코드: AT-034
    """
    # given: "a.pdf"가 있고 디스크 파일을 지운다
    uploaded = await attachment_env.uploaded(KIM, "a.pdf")
    await attachment_env.storage.delete(
        attachment_env.root,
        deal_location(uploaded.deal_code, uploaded.storage_key),
    )

    # when·then: 내려받으면 내용 없음 오류다
    with raises_with(AttachmentContentMissingError, CONTENT_MISSING):
        await attachment_env.download.execute(uploaded.id)


async def test_without_a_storage_location_the_download_is_unavailable(
    attachment_env: AttachmentEnv,
) -> None:
    """저장 위치 설정이 없으면 다운로드는 저장소 불가 오류다.

    테스트 코드: AT-035
    """
    # given: "a.pdf"가 있고 저장 위치 설정이 없다
    uploaded = await attachment_env.uploaded(KIM, "a.pdf")
    await attachment_env.remove_storage_settings()

    # when·then: 내려받으면 다운로드용 저장 위치 불가 오류다
    with raises_with(StorageUnavailableError, DOWNLOAD_UNAVAILABLE):
        await attachment_env.download.execute(uploaded.id)


async def test_a_file_that_exists_but_cannot_be_read_is_unavailable_not_missing(
    attachment_env: AttachmentEnv,
) -> None:
    """파일은 있으나 읽을 수 없으면 내용 없음이 아니라 저장소 불가 오류다.

    테스트 코드: AT-035
    """
    # given: "a.pdf"가 있고 읽기가 실패하게 한다
    uploaded = await attachment_env.uploaded(KIM, "a.pdf")
    attachment_env.storage.fail_reads = True

    # when·then: 내려받으면 다운로드용 저장 위치 불가 오류다
    with raises_with(StorageUnavailableError, DOWNLOAD_UNAVAILABLE):
        await attachment_env.download.execute(uploaded.id)


async def test_the_file_is_looked_up_under_the_current_storage_location(
    attachment_env: AttachmentEnv,
) -> None:
    """파일은 현재 저장 위치 아래에서 찾는다(위치가 바뀌면 내용 없음).

    테스트 코드: AT-034
    """
    from app.domain.storage.path import StoragePath  # noqa: PLC0415

    # given: "a.pdf"가 있고 저장 위치를 파일이 없는 다른 경로로 바꾼다
    uploaded = await attachment_env.uploaded(KIM, "a.pdf")
    async with attachment_env.env.uow_factory() as uow:
        await uow.storage_settings.save(
            StoragePath.parse("/data/moved"), updated_by=None, now=attachment_env.env.clock.now()
        )
        await uow.commit()

    # when·then: 내려받으면 내용 없음 오류다
    with pytest.raises(AttachmentContentMissingError):
        await attachment_env.download.execute(uploaded.id)


def test_a_read_failure_is_a_different_error_from_a_missing_file() -> None:
    """읽기 실패 오류는 파일 없음 오류와 서로 다른 계열이다."""
    from app.application.ports.file_storage import StoredFileMissingError  # noqa: PLC0415

    # when·then: 두 오류 클래스의 상속을 비교하면 서로의 하위 클래스가 아니다
    assert not issubclass(StorageNotReadableError, StoredFileMissingError)
    assert not issubclass(StoredFileMissingError, StorageNotReadableError)
