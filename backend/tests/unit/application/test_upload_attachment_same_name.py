"""UploadAttachment - 같은 이름(P2b AC-10·11): ask/skip/replace 결과와 교체 권한(Q2)."""

import unicodedata
from typing import TYPE_CHECKING

import pytest
from app.application.attachment.inputs import UploadOutcomeKind
from app.domain.attachment.errors import AttachmentNameTakenError, AttachmentReplaceForbiddenError

from app.domain.attachment.values import OnExists
from tests.support.expect import raises_with
from tests.unit.application.attachment_env import (
    BOSS,
    GONE_ADMIN,
    GONE_SALES,
    GONE_VIEWER,
    KIM,
    PARK,
    REPLACE_FORBIDDEN,
    TARGET,
)

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from tests.unit.application.attachment_env import AttachmentEnv


async def test_ask_conflicts_and_changes_nothing(attachment_env: AttachmentEnv) -> None:
    original = await attachment_env.uploaded(KIM, "a.pdf", b"old")
    before = await attachment_env.snapshot()

    with raises_with(AttachmentNameTakenError, "같은 이름의 파일이 이미 있습니다: a.pdf"):
        await attachment_env.put(KIM, "a.pdf", b"new", on_exists=OnExists.ASK)

    assert await attachment_env.snapshot() == before
    assert attachment_env.content_of(original) == b"old"


async def test_ask_is_the_default_when_the_choice_is_not_made(
    attachment_env: AttachmentEnv,
) -> None:
    await attachment_env.uploaded(KIM, "a.pdf", b"old")

    with pytest.raises(AttachmentNameTakenError):
        await attachment_env.put(KIM, "a.pdf", b"new")


async def test_skip_returns_no_attachment_and_changes_nothing(
    attachment_env: AttachmentEnv,
) -> None:
    await attachment_env.uploaded(KIM, "a.pdf", b"old")
    before = await attachment_env.snapshot()

    outcome = await attachment_env.put(KIM, "a.pdf", b"new", on_exists=OnExists.SKIP)

    assert outcome.kind is UploadOutcomeKind.SKIPPED
    assert outcome.attachment is None
    assert await attachment_env.snapshot() == before


async def test_replace_keeps_the_id_and_swaps_content_description_and_time(
    attachment_env: AttachmentEnv,
) -> None:
    original = await attachment_env.uploaded(KIM, "a.pdf", b"old")

    outcome = await attachment_env.put(
        KIM,
        "a.pdf",
        b"newer content",
        on_exists=OnExists.REPLACE,
        description="새 설명",
        mime="text/plain",
    )

    replaced = outcome.attachment
    now = attachment_env.env.clock.now()
    assert outcome.kind is UploadOutcomeKind.REPLACED
    assert replaced.id == original.id
    assert (replaced.description, replaced.size, replaced.mime) == ("새 설명", 13, "text/plain")
    assert replaced.uploaded_at == replaced.updated_at == now
    assert replaced.created_at == original.created_at
    assert (await attachment_env.stored(original.id)).size == 13
    assert len(await attachment_env.rows()) == 1


async def test_replace_writes_the_new_content_and_removes_the_old_disk_file(
    attachment_env: AttachmentEnv,
) -> None:
    original = await attachment_env.uploaded(KIM, "a.pdf", b"old")

    outcome = await attachment_env.put(KIM, "a.pdf", b"new", on_exists=OnExists.REPLACE)

    assert attachment_env.content_of(original) is None
    assert attachment_env.content_of(outcome.attachment) == b"new"
    assert outcome.attachment.storage_key != original.storage_key
    assert attachment_env.storage.file_count() == 1


async def test_replace_records_one_replace_entry_and_touches_the_deal(
    attachment_env: AttachmentEnv,
) -> None:
    await attachment_env.uploaded(KIM, "a.pdf", b"old")

    await attachment_env.put(KIM, "a.pdf", b"new", on_exists=OnExists.REPLACE)

    assert await attachment_env.history() == [
        (TARGET, "", "업로드 a.pdf"),
        (TARGET, "", "교체 a.pdf"),
    ]
    assert await attachment_env.deal_updated_at() == attachment_env.env.clock.now()


async def test_an_admin_replacing_takes_over_as_the_uploader(attachment_env: AttachmentEnv) -> None:
    await attachment_env.uploaded(KIM, "a.pdf", b"old")

    outcome = await attachment_env.put(BOSS, "a.pdf", b"new", on_exists=OnExists.REPLACE)

    assert outcome.attachment.uploaded_by == BOSS.user_id
    (_, replaced) = await attachment_env.entries()
    assert replaced.changed_by == BOSS.user_id


async def test_the_name_is_compared_after_nfc_normalization(attachment_env: AttachmentEnv) -> None:
    await attachment_env.uploaded(KIM, "한글.pdf", b"old")
    decomposed = unicodedata.normalize("NFD", "한글.pdf")

    with pytest.raises(AttachmentNameTakenError):
        await attachment_env.put(KIM, decomposed, b"new")
    outcome = await attachment_env.put(KIM, decomposed, b"new", on_exists=OnExists.REPLACE)

    assert outcome.kind is UploadOutcomeKind.REPLACED
    assert outcome.attachment.file_name.value == "한글.pdf"


@pytest.mark.parametrize(
    ("uploader", "requester"),
    [
        (KIM, KIM),
        (KIM, BOSS),
        (BOSS, BOSS),
        (GONE_SALES, KIM),
        (GONE_SALES, BOSS),
    ],
)
async def test_replace_is_allowed_for_the_uploader_an_admin_and_for_sales_of_a_resigned_sales_file(
    attachment_env: AttachmentEnv, uploader: Actor, requester: Actor
) -> None:
    original = await attachment_env.seed(uploader, "a.pdf", b"old")

    outcome = await attachment_env.put(
        requester,
        "a.pdf",
        b"new",
        on_exists=OnExists.REPLACE,
    )

    assert outcome.kind is UploadOutcomeKind.REPLACED
    assert outcome.attachment.id == original.id
    assert attachment_env.content_of(outcome.attachment) == b"new"


@pytest.mark.parametrize(
    ("uploader", "requester"),
    [
        (KIM, PARK),
        (BOSS, KIM),
        (GONE_ADMIN, KIM),
        (GONE_VIEWER, KIM),
    ],
)
async def test_replace_by_someone_who_may_not_delete_the_file_is_forbidden_and_changes_nothing(
    attachment_env: AttachmentEnv, uploader: Actor, requester: Actor
) -> None:
    await attachment_env.seed(uploader, "a.pdf", b"old")
    before = await attachment_env.snapshot()

    with raises_with(AttachmentReplaceForbiddenError, REPLACE_FORBIDDEN):
        await attachment_env.put(
            requester,
            "a.pdf",
            b"new",
            on_exists=OnExists.REPLACE,
        )

    assert await attachment_env.snapshot() == before


async def test_ask_by_another_sales_is_a_conflict_not_a_permission_error(
    attachment_env: AttachmentEnv,
) -> None:
    await attachment_env.uploaded(KIM, "a.pdf", b"old")

    with pytest.raises(AttachmentNameTakenError):
        await attachment_env.put(PARK, "a.pdf", b"new", on_exists=OnExists.ASK)


async def test_skip_by_another_sales_is_allowed_whoever_owns_the_file(
    attachment_env: AttachmentEnv,
) -> None:
    await attachment_env.uploaded(KIM, "a.pdf", b"old")

    outcome = await attachment_env.put(PARK, "a.pdf", b"new", on_exists=OnExists.SKIP)

    assert outcome.kind is UploadOutcomeKind.SKIPPED
