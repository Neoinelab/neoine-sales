"""DeleteDeal과 첨부(P2b AC-15): 커밋 뒤 Deal 디렉터리 삭제, 실패는 경고 로그만, 삭제 영향 건수."""

import logging
from typing import TYPE_CHECKING

import pytest

from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.inputs import Actor
from app.application.ports.deal_repository import DealDeletionImpact
from app.domain.attachment.values import OnExists
from app.domain.auth.principal import Role
from app.domain.deal.errors import DealCodeMismatchError, DealDeleteForbiddenError
from tests.factories_deal import SALES
from tests.fakes.commit_failure import COMMIT_FAILED, commit_failing_factory
from tests.support.auth_seed import seed_user
from tests.support.expect import raises_with
from tests.unit.application.attachment_env import KIM, ROOT_PATH

if TYPE_CHECKING:
    from tests.unit.application.attachment_env import AttachmentEnv


async def _delete(attachment_env: AttachmentEnv, code: str | None = None) -> None:
    target = code or attachment_env.code
    await attachment_env.env.delete.execute(target, target, SALES)


async def test_deleting_the_deal_removes_its_attachment_rows_and_its_directory(
    attachment_env: AttachmentEnv,
) -> None:
    await attachment_env.uploaded(KIM, "a.pdf", b"1")
    await attachment_env.uploaded(KIM, "b.pdf", b"2")
    directory = f"{ROOT_PATH}/{attachment_env.code}"
    assert attachment_env.storage.entries(directory) != []

    await _delete(attachment_env)

    assert attachment_env.env.uow.attachments._items == {}
    assert not attachment_env.storage.dir_exists(directory)
    assert attachment_env.storage.file_count() == 0


async def test_other_deals_files_and_the_storage_root_stay(attachment_env: AttachmentEnv) -> None:
    other = await attachment_env.env.new_deal()
    other_code = other.item.deal.id.value
    await attachment_env.uploaded(KIM, "a.pdf", b"mine")
    kept = await attachment_env.put(KIM, "b.pdf", b"theirs", code=other_code)

    await _delete(attachment_env)

    assert attachment_env.content_of(kept.attachment) == b"theirs"
    assert attachment_env.storage.dir_exists(ROOT_PATH)
    assert [a.id for a in attachment_env.env.uow.attachments._items.values()] == [
        kept.attachment.id
    ]


async def test_a_deal_without_files_is_deleted_without_trouble(
    attachment_env: AttachmentEnv,
) -> None:
    await _delete(attachment_env)

    assert attachment_env.env.uow.deals._items == {}


async def test_the_deal_is_deleted_even_when_its_directory_cannot_be_removed(
    attachment_env: AttachmentEnv, caplog: pytest.LogCaptureFixture
) -> None:
    await attachment_env.uploaded(KIM, "a.pdf", b"stuck")
    attachment_env.storage.fail_deletes = True
    caplog.set_level(logging.WARNING)

    await _delete(attachment_env)

    assert attachment_env.env.uow.deals._items == {}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(attachment_env.code in r.getMessage() for r in warnings)


async def test_a_deal_is_deleted_without_a_storage_location_and_files_are_left_alone(
    attachment_env: AttachmentEnv,
) -> None:
    uploaded = await attachment_env.uploaded(KIM, "a.pdf", b"stays")
    await attachment_env.remove_storage_settings()

    await _delete(attachment_env)

    assert attachment_env.env.uow.deals._items == {}
    assert attachment_env.content_of(uploaded) == b"stays"


async def test_a_refused_delete_does_not_touch_the_files(attachment_env: AttachmentEnv) -> None:
    uploaded = await attachment_env.uploaded(KIM, "a.pdf", b"keep")
    stranger = await seed_user(attachment_env.env.uow_factory, "stranger")
    code = attachment_env.code
    with pytest.raises(DealDeleteForbiddenError):
        await attachment_env.env.delete.execute(code, code, Actor(stranger.id, Role.SALES))
    with pytest.raises(DealCodeMismatchError):
        await attachment_env.env.delete.execute(code, "wrong", SALES)

    assert attachment_env.content_of(uploaded) == b"keep"
    assert len(attachment_env.env.uow.attachments._items) == 1


async def test_a_failed_commit_keeps_the_deal_and_its_files(attachment_env: AttachmentEnv) -> None:
    uploaded = await attachment_env.uploaded(KIM, "a.pdf", b"keep")
    env = attachment_env.env
    broken = DeleteDeal(commit_failing_factory(env.uow), env.clock, attachment_env.storage)

    with raises_with(RuntimeError, COMMIT_FAILED):
        await broken.execute(attachment_env.code, attachment_env.code, SALES)

    assert attachment_env.content_of(uploaded) == b"keep"
    assert len(env.uow.deals._items) == 1


async def test_the_deletion_impact_counts_the_attachments_of_that_deal(
    attachment_env: AttachmentEnv,
) -> None:
    other = await attachment_env.env.new_deal()
    await attachment_env.uploaded(KIM, "a.pdf")
    await attachment_env.uploaded(KIM, "b.pdf")
    await attachment_env.put(KIM, "c.pdf", code=other.item.deal.id.value)

    impact = await attachment_env.env.impact.execute(attachment_env.code)

    assert impact == DealDeletionImpact(
        history_count=3, action_count=0, attachment_count=2, partner_meeting_count=0
    )


async def test_the_impact_counts_a_replaced_file_once_and_drops_a_deleted_one(
    attachment_env: AttachmentEnv,
) -> None:
    first = await attachment_env.uploaded(KIM, "a.pdf")
    await attachment_env.put(KIM, "a.pdf", b"v2", on_exists=OnExists.REPLACE)
    second = await attachment_env.uploaded(KIM, "b.pdf")
    await attachment_env.delete.execute(second.id, KIM)

    impact = await attachment_env.env.impact.execute(attachment_env.code)

    assert impact.attachment_count == 1
    assert first.id in attachment_env.env.uow.attachments._items
