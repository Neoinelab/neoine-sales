"""UploadAttachment - 저장소 쪽 실패(P2b AC-08·09): 쓰기 불가 503, 스트림 한도, 읽기·커밋 실패."""

from typing import TYPE_CHECKING

import pytest
from app.application.attachment.inputs import UploadOutcomeKind
from app.application.attachment.upload_attachment import UploadAttachment

from app.application.storage.errors import UPLOAD_UNAVAILABLE, StorageUnavailableError
from app.domain.attachment.values import FILE_TOO_LARGE, MAX_FILE_BYTES, OnExists
from app.domain.common.errors import InvalidValueError
from tests.fakes.commit_failure import COMMIT_FAILED, commit_failing_factory
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
    attachment_env.storage.block("/data")
    before = await attachment_env.snapshot()

    with raises_with(StorageUnavailableError, UPLOAD_UNAVAILABLE):
        await attachment_env.put(KIM, "a.pdf", b"x")

    assert await attachment_env.snapshot() == before


async def test_a_stream_longer_than_the_limit_is_rejected_whatever_was_declared(
    attachment_env: AttachmentEnv,
) -> None:
    before = await attachment_env.snapshot()

    with raises_with(InvalidValueError, FILE_TOO_LARGE):
        await attachment_env.put(
            KIM, "big.bin", b"", declared_size=10, source=ZeroSource(MAX_FILE_BYTES + 1)
        )

    assert await attachment_env.snapshot() == before
    assert attachment_env.storage.file_count() == 0


async def test_a_stream_of_exactly_the_limit_is_stored(attachment_env: AttachmentEnv) -> None:
    outcome = await attachment_env.put(
        KIM, "max.bin", b"", declared_size=MAX_FILE_BYTES, source=ZeroSource(MAX_FILE_BYTES)
    )

    assert outcome.kind is UploadOutcomeKind.UPLOADED
    assert outcome.attachment.size == MAX_FILE_BYTES
    assert attachment_env.storage.file_count() == 1


async def test_a_connection_that_breaks_while_reading_leaves_nothing_behind(
    attachment_env: AttachmentEnv,
) -> None:
    before = await attachment_env.snapshot()

    with pytest.raises(ClientGone):
        await attachment_env.put(
            KIM, "a.pdf", b"", declared_size=None, source=FailingSource(ClientGone())
        )

    assert await attachment_env.snapshot() == before


async def test_a_failed_commit_removes_the_new_file_and_raises(
    attachment_env: AttachmentEnv,
) -> None:
    broken = _upload_with_failing_commit(attachment_env)
    before = await attachment_env.snapshot()

    with raises_with(RuntimeError, COMMIT_FAILED):
        await broken.execute(attachment_env.code, attachment_env.make_input("a.pdf", b"x"), KIM)

    assert await attachment_env.snapshot() == before
    assert attachment_env.storage.file_count() == 0


async def test_a_failed_commit_of_a_replacement_keeps_the_old_file_and_removes_the_new_one(
    attachment_env: AttachmentEnv,
) -> None:
    original = await attachment_env.uploaded(KIM, "a.pdf", b"old")
    broken = _upload_with_failing_commit(attachment_env)
    before = await attachment_env.snapshot()
    replacing = attachment_env.make_input("a.pdf", b"new", on_exists=OnExists.REPLACE)

    with raises_with(RuntimeError, COMMIT_FAILED):
        await broken.execute(attachment_env.code, replacing, KIM)

    assert await attachment_env.snapshot() == before
    assert attachment_env.content_of(original) == b"old"
    assert attachment_env.storage.file_count() == 1


async def test_a_replacement_succeeds_even_when_the_old_file_cannot_be_removed(
    attachment_env: AttachmentEnv,
) -> None:
    original = await attachment_env.uploaded(KIM, "a.pdf", b"old")
    attachment_env.storage.fail_deletes = True

    outcome = await attachment_env.put(BOSS, "a.pdf", b"new", on_exists=OnExists.REPLACE)

    assert outcome.kind is UploadOutcomeKind.REPLACED
    assert attachment_env.content_of(outcome.attachment) == b"new"
    assert (await attachment_env.stored(original.id)).storage_key == outcome.attachment.storage_key
