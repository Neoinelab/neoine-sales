"""UploadAttachment - 저장소 쪽 실패: 쓰기 불가 503, 스트림 한도, 읽기·커밋 실패."""

from typing import TYPE_CHECKING

import pytest

from app.application.attachment.inputs import UploadOutcomeKind
from app.application.attachment.upload_attachment import UploadAttachment
from app.application.storage.errors import UPLOAD_UNAVAILABLE, StorageUnavailableError
from app.domain.attachment.values import FILE_TOO_LARGE, MAX_FILE_BYTES, OnExists
from app.domain.common.errors import InvalidValueError
from tests.fakes.commit_failure import (
    COMMIT_FAILED,
    EXIT_FAILED,
    commit_failing_factory,
    exit_failing_factory,
)
from tests.fakes.sources import ClientGone, FailingSource, ZeroSource
from tests.support.expect import raises_with
from tests.unit.application.attachment_env import BOSS, KIM

if TYPE_CHECKING:
    from tests.unit.application.attachment_env import AttachmentEnv


def _upload_with_failing_commit(attachment_env: AttachmentEnv) -> UploadAttachment:
    """저장소 쓰기까지는 정상이고 DB commit만 실패하는 UploadAttachment."""
    env = attachment_env.env
    return UploadAttachment(commit_failing_factory(env.uow), env.clock, attachment_env.storage)


async def test_a_storage_location_that_cannot_be_written_is_unavailable(
    attachment_env: AttachmentEnv,
) -> None:
    """저장 위치에 쓸 수 없으면 저장소 불가 오류이고 아무것도 남지 않는다.

    테스트 코드: AT-015
    """
    # given: 쓸 수 없는 저장 위치와 현재 상태
    attachment_env.storage.block("/data")
    before = await attachment_env.snapshot()

    # when·then: 업로드하면 업로드용 저장 위치 불가 오류다
    with raises_with(StorageUnavailableError, UPLOAD_UNAVAILABLE):
        await attachment_env.put(KIM, "a.pdf", b"x")

    # then: 저장 상태가 그대로다
    assert await attachment_env.snapshot() == before


async def test_a_stream_longer_than_the_limit_is_rejected_whatever_was_declared(
    attachment_env: AttachmentEnv,
) -> None:
    """선언 크기와 무관하게 실제 내용이 한도를 넘으면 거절되고 파일이 남지 않는다.

    테스트 코드: AT-011
    """
    # given: 업로드 전 상태
    before = await attachment_env.snapshot()

    # when·then: 선언은 작고 실제는 100MB+1바이트인 파일을 올리면 크기 초과 오류다
    with raises_with(InvalidValueError, FILE_TOO_LARGE):
        await attachment_env.put(
            KIM, "big.bin", b"", declared_size=10, source=ZeroSource(MAX_FILE_BYTES + 1)
        )

    # then: 저장 상태가 그대로이고 디스크 파일이 없다
    assert await attachment_env.snapshot() == before
    assert attachment_env.storage.file_count() == 0


async def test_a_stream_of_exactly_the_limit_is_stored(attachment_env: AttachmentEnv) -> None:
    """정확히 100MB인 내용은 저장된다.

    테스트 코드: AT-005
    """
    # when: 정확히 100MB를 올린다 (전제: 저장 위치가 설정된 Deal)
    outcome = await attachment_env.put(
        KIM, "max.bin", b"", declared_size=MAX_FILE_BYTES, source=ZeroSource(MAX_FILE_BYTES)
    )

    # then: 새 업로드이고 크기가 한도와 같으며 파일이 하나 저장된다
    assert outcome.kind is UploadOutcomeKind.UPLOADED
    assert outcome.attachment.size == MAX_FILE_BYTES
    assert attachment_env.storage.file_count() == 1


async def test_a_connection_that_breaks_while_reading_leaves_nothing_behind(
    attachment_env: AttachmentEnv,
) -> None:
    """읽는 도중 연결이 끊기면 쓰던 파일이 남지 않는다.

    테스트 코드: AT-025
    """
    # given: 업로드 전 상태
    before = await attachment_env.snapshot()

    # when·then: 내용 스트림이 중간에 오류를 내는 업로드를 하면 그 오류로 끝난다
    with pytest.raises(ClientGone):
        await attachment_env.put(
            KIM, "a.pdf", b"", declared_size=None, source=FailingSource(ClientGone())
        )

    # then: 저장 상태가 그대로다
    assert await attachment_env.snapshot() == before


async def test_a_failed_commit_removes_the_new_file_and_raises(
    attachment_env: AttachmentEnv,
) -> None:
    """커밋이 실패하면 오류를 내고 새 파일을 지운다.

    테스트 코드: AT-024
    """
    # given: 커밋만 실패하는 업로드 유스케이스와 현재 상태
    broken = _upload_with_failing_commit(attachment_env)
    before = await attachment_env.snapshot()

    # when·then: 새 파일을 올리면 커밋 실패 오류다
    with raises_with(RuntimeError, COMMIT_FAILED):
        await broken.execute(attachment_env.code, attachment_env.make_input("a.pdf", b"x"), KIM)

    # then: 저장 상태가 그대로이고 디스크 파일이 없다
    assert await attachment_env.snapshot() == before
    assert attachment_env.storage.file_count() == 0


async def test_a_failed_commit_of_a_replacement_keeps_the_old_file_and_removes_the_new_one(
    attachment_env: AttachmentEnv,
) -> None:
    """교체의 커밋이 실패하면 이전 파일은 남고 새 파일은 지워진다.

    테스트 코드: AT-024
    """
    # given: "a.pdf"(old)와 커밋만 실패하는 유스케이스, 교체 입력
    original = await attachment_env.uploaded(KIM, "a.pdf", b"old")
    broken = _upload_with_failing_commit(attachment_env)
    before = await attachment_env.snapshot()
    replacing = attachment_env.make_input("a.pdf", b"new", on_exists=OnExists.REPLACE)

    # when·then: replace로 올리면 커밋 실패 오류다
    with raises_with(RuntimeError, COMMIT_FAILED):
        await broken.execute(attachment_env.code, replacing, KIM)

    # then: 상태가 그대로이고 첨부는 old를 가리키며 디스크 파일은 이전 것 하나뿐이다
    assert await attachment_env.snapshot() == before
    assert attachment_env.content_of(original) == b"old"
    assert attachment_env.storage.file_count() == 1


async def test_a_replacement_succeeds_even_when_the_old_file_cannot_be_removed(
    attachment_env: AttachmentEnv,
) -> None:
    """이전 파일을 지우지 못해도 교체는 성공한다.

    테스트 코드: AT-024
    """
    # given: "a.pdf"(old)가 있고 디스크 삭제가 실패하게 한다
    original = await attachment_env.uploaded(KIM, "a.pdf", b"old")
    attachment_env.storage.fail_deletes = True

    # when: replace로 올린다
    outcome = await attachment_env.put(BOSS, "a.pdf", b"new", on_exists=OnExists.REPLACE)

    # then: 교체 성공이고 새 내용이 저장되며 행이 새 키를 가리킨다
    assert outcome.kind is UploadOutcomeKind.REPLACED
    assert attachment_env.content_of(outcome.attachment) == b"new"
    assert (await attachment_env.stored(original.id)).storage_key == outcome.attachment.storage_key


async def test_an_error_after_a_successful_commit_keeps_the_committed_new_file(
    attachment_env: AttachmentEnv,
) -> None:
    """커밋이 끝난 뒤 오류가 나도 새 파일은 남는다.

    테스트 코드: AT-024
    """
    # given: 커밋 뒤에 오류를 내는 업로드 유스케이스
    env = attachment_env.env
    upload = UploadAttachment(exit_failing_factory(env.uow), env.clock, attachment_env.storage)

    # when·then: 새 파일을 올리면 그 오류가 난다
    with raises_with(RuntimeError, EXIT_FAILED):
        await upload.execute(attachment_env.code, attachment_env.make_input("a.pdf", b"x"), KIM)

    # then: 커밋된 행이 하나 있고
    rows = await attachment_env.rows()
    assert [r.file_name.value for r in rows] == ["a.pdf"]  # 커밋된 행
    # then: 그 행이 가리키는 파일이 디스크에 남아 있다
    assert attachment_env.content_of(rows[0]) == b"x"  # 그 행이 가리키는 파일은 남아 있다


async def test_an_error_after_a_committed_replacement_keeps_the_new_file(
    attachment_env: AttachmentEnv,
) -> None:
    """교체가 커밋된 뒤 오류가 나도 새 파일은 남는다.

    테스트 코드: AT-024
    """
    # given: "a.pdf"(old)와 커밋 뒤 오류를 내는 유스케이스
    await attachment_env.uploaded(KIM, "a.pdf", b"old")
    env = attachment_env.env
    upload = UploadAttachment(exit_failing_factory(env.uow), env.clock, attachment_env.storage)
    replacing = attachment_env.make_input("a.pdf", b"new", on_exists=OnExists.REPLACE)

    # when·then: replace로 올리면 그 오류가 난다
    with raises_with(RuntimeError, EXIT_FAILED):
        await upload.execute(attachment_env.code, replacing, KIM)

    # then: 행이 하나이고 새 내용이 디스크에 남아 있다
    (row,) = await attachment_env.rows()
    assert attachment_env.content_of(row) == b"new"
