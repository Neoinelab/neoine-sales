"""ListAttachments / GetAttachment(P2b AC-12): 업로드 시각 최신순 목록과 단건 조회."""

from typing import TYPE_CHECKING

import pytest

from app.domain.attachment.errors import AttachmentNotFoundError
from app.domain.attachment.values import AttachmentId
from app.domain.deal.errors import DealNotFoundError
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.attachment_env import DEAL_NOT_FOUND, KIM, NOT_FOUND, PARK

if TYPE_CHECKING:
    from tests.unit.application.attachment_env import AttachmentEnv


async def test_a_deal_without_attachments_has_an_empty_list(attachment_env: AttachmentEnv) -> None:
    assert list(await attachment_env.list.execute(attachment_env.code)) == []


async def test_the_list_is_newest_upload_first(attachment_env: AttachmentEnv) -> None:
    first = await attachment_env.uploaded(KIM, "first.pdf")
    second = await attachment_env.uploaded(PARK, "second.pdf")
    third = await attachment_env.uploaded(KIM, "third.pdf")

    found = await attachment_env.list.execute(attachment_env.code)

    assert [a.id for a in found] == [third.id, second.id, first.id]


async def test_uploads_at_the_same_time_are_ordered_by_id_descending(
    attachment_env: AttachmentEnv,
) -> None:
    same_time = [await attachment_env.seed(KIM, f"{n}.pdf") for n in range(4)]

    found = await attachment_env.list.execute(attachment_env.code)

    assert [a.id for a in found] == sorted((a.id for a in same_time), reverse=True)


async def test_a_replaced_file_moves_to_the_top(attachment_env: AttachmentEnv) -> None:
    from app.domain.attachment.values import OnExists  # noqa: PLC0415

    old = await attachment_env.uploaded(KIM, "old.pdf")
    newer = await attachment_env.uploaded(KIM, "newer.pdf")
    await attachment_env.put(KIM, "old.pdf", b"again", on_exists=OnExists.REPLACE)

    found = await attachment_env.list.execute(attachment_env.code)

    assert [a.id for a in found] == [old.id, newer.id]


async def test_other_deals_files_are_not_listed(attachment_env: AttachmentEnv) -> None:
    other = await attachment_env.env.new_deal()
    mine = await attachment_env.uploaded(KIM, "mine.pdf")
    await attachment_env.put(KIM, "theirs.pdf", code=other.item.deal.id.value)

    found = await attachment_env.list.execute(attachment_env.code)

    assert [a.id for a in found] == [mine.id]


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code", ""])
async def test_listing_a_missing_or_malformed_deal_is_not_found(
    attachment_env: AttachmentEnv, code: str
) -> None:
    with raises_with(DealNotFoundError, DEAL_NOT_FOUND):
        await attachment_env.list.execute(code)


async def test_get_returns_the_attachment(attachment_env: AttachmentEnv) -> None:
    uploaded = await attachment_env.uploaded(KIM, "a.pdf", b"12345")

    found = await attachment_env.get.execute(uploaded.id)

    assert (found.id, found.file_name.value, found.size) == (uploaded.id, "a.pdf", 5)
    assert found.uploaded_by == KIM.user_id


async def test_get_of_an_unknown_id_is_not_found(attachment_env: AttachmentEnv) -> None:
    with raises_with(AttachmentNotFoundError, NOT_FOUND):
        await attachment_env.get.execute(AttachmentId(new_id()))
