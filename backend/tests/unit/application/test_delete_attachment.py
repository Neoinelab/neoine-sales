"""DeleteAttachment(P2b AC-14): 판정 순서 404 -> 권한 403, 행·파일 삭제, 이력, Deal 수정 시각."""

import logging
from typing import TYPE_CHECKING

import pytest

from app.application.attachment.delete_attachment import DeleteAttachment
from app.domain.attachment.errors import AttachmentDeleteForbiddenError, AttachmentNotFoundError
from app.domain.attachment.values import AttachmentId
from tests.fakes.commit_failure import COMMIT_FAILED, commit_failing_factory
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.attachment_env import (
    BOSS,
    DELETE_FORBIDDEN,
    GONE_ADMIN,
    GONE_SALES,
    GONE_VIEWER,
    KIM,
    NOT_FOUND,
    PARK,
    TARGET,
    VIEWER,
)

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from tests.unit.application.attachment_env import AttachmentEnv


async def test_the_uploader_deletes_the_row_and_the_disk_file(
    attachment_env: AttachmentEnv,
) -> None:
    attachment = await attachment_env.uploaded(KIM, "a.pdf", b"data")

    await attachment_env.delete.execute(attachment.id, KIM)

    with pytest.raises(AttachmentNotFoundError):
        await attachment_env.stored(attachment.id)
    assert attachment_env.content_of(attachment) is None
    assert attachment_env.storage.file_count() == 0


async def test_the_delete_is_recorded_in_the_deal_history_by_the_requester(
    attachment_env: AttachmentEnv,
) -> None:
    attachment = await attachment_env.uploaded(KIM, "a.pdf")
    attachment_env.env.clock.advance(60)

    await attachment_env.delete.execute(attachment.id, BOSS)

    assert await attachment_env.history() == [
        (TARGET, "", "업로드 a.pdf"),
        (TARGET, "", "삭제 a.pdf"),
    ]
    deleted = (await attachment_env.entries())[-1]
    assert deleted.changed_by == BOSS.user_id
    assert deleted.changed_at == attachment_env.env.clock.now()


async def test_the_deal_modification_time_becomes_the_delete_time(
    attachment_env: AttachmentEnv,
) -> None:
    attachment = await attachment_env.uploaded(KIM, "a.pdf")
    attachment_env.env.clock.advance(60)

    await attachment_env.delete.execute(attachment.id, KIM)

    assert await attachment_env.deal_updated_at() == attachment_env.env.clock.now()


async def test_only_the_named_file_is_removed(attachment_env: AttachmentEnv) -> None:
    gone = await attachment_env.uploaded(KIM, "gone.pdf", b"1")
    kept = await attachment_env.uploaded(KIM, "kept.pdf", b"2")

    await attachment_env.delete.execute(gone.id, KIM)

    assert [a.id for a in await attachment_env.rows()] == [kept.id]
    assert attachment_env.content_of(kept) == b"2"


@pytest.mark.parametrize(
    ("uploader", "requester"),
    [
        (KIM, KIM),
        (KIM, BOSS),
        (BOSS, BOSS),
        (GONE_SALES, KIM),
        (GONE_ADMIN, BOSS),
        (GONE_VIEWER, BOSS),
    ],
)
async def test_delete_is_allowed_for_the_uploader_admins_and_sales_of_a_resigned_sales_file(
    attachment_env: AttachmentEnv, uploader: Actor, requester: Actor
) -> None:
    attachment = await attachment_env.seed(uploader, "a.pdf")

    await attachment_env.delete.execute(attachment.id, requester)

    assert await attachment_env.rows() == []


@pytest.mark.parametrize(
    ("uploader", "requester"),
    [
        (KIM, PARK),
        (BOSS, KIM),
        (GONE_ADMIN, KIM),
        (GONE_VIEWER, KIM),
        (KIM, VIEWER),
        (VIEWER, VIEWER),
    ],
)
async def test_delete_by_someone_without_the_right_is_forbidden_and_keeps_everything(
    attachment_env: AttachmentEnv, uploader: Actor, requester: Actor
) -> None:
    attachment = await attachment_env.seed(uploader, "a.pdf", b"keep")
    before = await attachment_env.snapshot()

    with raises_with(AttachmentDeleteForbiddenError, DELETE_FORBIDDEN):
        await attachment_env.delete.execute(attachment.id, requester)

    assert await attachment_env.snapshot() == before
    assert attachment_env.content_of(attachment) == b"keep"


async def test_an_unknown_id_is_not_found_whoever_asks(attachment_env: AttachmentEnv) -> None:
    missing = AttachmentId(new_id())

    for actor in (KIM, PARK, BOSS, VIEWER):
        with raises_with(AttachmentNotFoundError, NOT_FOUND):
            await attachment_env.delete.execute(missing, actor)


async def test_deleting_twice_is_not_found_the_second_time(attachment_env: AttachmentEnv) -> None:
    attachment = await attachment_env.uploaded(KIM, "a.pdf")
    await attachment_env.delete.execute(attachment.id, KIM)

    with raises_with(AttachmentNotFoundError, NOT_FOUND):
        await attachment_env.delete.execute(attachment.id, KIM)


async def test_the_row_is_deleted_even_when_the_disk_file_cannot_be_removed(
    attachment_env: AttachmentEnv, caplog: pytest.LogCaptureFixture
) -> None:
    attachment = await attachment_env.uploaded(KIM, "a.pdf", b"stuck")
    attachment_env.storage.fail_deletes = True
    caplog.set_level(logging.WARNING)

    await attachment_env.delete.execute(attachment.id, KIM)

    with pytest.raises(AttachmentNotFoundError):
        await attachment_env.stored(attachment.id)
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert await attachment_env.history() == [
        (TARGET, "", "업로드 a.pdf"),
        (TARGET, "", "삭제 a.pdf"),
    ]


async def test_the_row_is_deleted_when_no_storage_location_is_configured(
    attachment_env: AttachmentEnv,
) -> None:
    attachment = await attachment_env.uploaded(KIM, "a.pdf")
    await attachment_env.remove_storage_settings()

    await attachment_env.delete.execute(attachment.id, KIM)

    assert await attachment_env.rows() == []


async def test_a_failed_commit_keeps_the_row_and_the_disk_file(
    attachment_env: AttachmentEnv,
) -> None:
    attachment = await attachment_env.uploaded(KIM, "a.pdf", b"data")
    env = attachment_env.env
    broken = DeleteAttachment(commit_failing_factory(env.uow), env.clock, attachment_env.storage)
    before = await attachment_env.snapshot()

    with raises_with(RuntimeError, COMMIT_FAILED):
        await broken.execute(attachment.id, KIM)

    assert await attachment_env.snapshot() == before
    assert attachment_env.content_of(attachment) == b"data"
