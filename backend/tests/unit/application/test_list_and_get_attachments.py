"""ListAttachments / GetAttachment: 업로드 시각 최신순 목록과 단건 조회."""

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
    """첨부가 없는 Deal의 목록은 비어 있다.

    테스트 코드: AT-027
    """
    # when: 첨부가 없는 Deal의 목록을 읽는다
    found = list(await attachment_env.list.execute(attachment_env.code))

    # then: 목록이 비어 있다
    assert found == []


async def test_the_list_is_newest_upload_first(attachment_env: AttachmentEnv) -> None:
    """목록은 최신 업로드 순이다.

    테스트 코드: AT-026
    """
    # given: 시각이 다른 세 파일이 올라가 있다
    first = await attachment_env.uploaded(KIM, "first.pdf")
    second = await attachment_env.uploaded(PARK, "second.pdf")
    third = await attachment_env.uploaded(KIM, "third.pdf")

    # when: 목록을 읽는다
    found = await attachment_env.list.execute(attachment_env.code)

    # then: 나중에 올린 순서로 나온다
    assert [a.id for a in found] == [third.id, second.id, first.id]


async def test_uploads_at_the_same_time_are_ordered_by_id_descending(
    attachment_env: AttachmentEnv,
) -> None:
    """같은 시각 업로드는 id 내림차순이다.

    테스트 코드: AT-026
    """
    # given: 같은 시각의 파일 네 개
    same_time = [await attachment_env.seed(KIM, f"{n}.pdf") for n in range(4)]

    # when: 목록을 읽는다
    found = await attachment_env.list.execute(attachment_env.code)

    # then: id 내림차순이다
    assert [a.id for a in found] == sorted((a.id for a in same_time), reverse=True)


async def test_a_replaced_file_moves_to_the_top(attachment_env: AttachmentEnv) -> None:
    """교체한 파일은 업로드 시각이 바뀌어 맨 위로 온다.

    테스트 코드: AT-026
    """
    from app.domain.attachment.values import OnExists  # noqa: PLC0415

    # given: 두 파일이 올라가 있고 첫 파일을 replace로 다시 올린다
    old = await attachment_env.uploaded(KIM, "old.pdf")
    newer = await attachment_env.uploaded(KIM, "newer.pdf")
    await attachment_env.put(KIM, "old.pdf", b"again", on_exists=OnExists.REPLACE)

    # when: 목록을 읽는다
    found = await attachment_env.list.execute(attachment_env.code)

    # then: 교체한 파일이 맨 위다
    assert [a.id for a in found] == [old.id, newer.id]


async def test_other_deals_files_are_not_listed(attachment_env: AttachmentEnv) -> None:
    """다른 Deal의 파일은 목록에 나오지 않는다.

    테스트 코드: AT-026
    """
    # given: 이 Deal과 다른 Deal에 각각 파일이 있다
    other = await attachment_env.env.new_deal()
    mine = await attachment_env.uploaded(KIM, "mine.pdf")
    await attachment_env.put(KIM, "theirs.pdf", code=other.item.deal.id.value)

    # when: 이 Deal의 목록을 읽는다
    found = await attachment_env.list.execute(attachment_env.code)

    # then: 이 Deal의 파일만 나온다
    assert [a.id for a in found] == [mine.id]


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code", ""])
async def test_listing_a_missing_or_malformed_deal_is_not_found(
    attachment_env: AttachmentEnv, code: str
) -> None:
    """없는 Deal·형식이 틀린 code의 목록은 Deal 없음 오류다.

    테스트 코드: AT-028
    """
    # when·then: 목록을 읽으면 Deal 없음 오류다
    with raises_with(DealNotFoundError, DEAL_NOT_FOUND):
        await attachment_env.list.execute(code)


async def test_get_returns_the_attachment(attachment_env: AttachmentEnv) -> None:
    """id로 첨부 한 건을 읽는다.

    테스트 코드: AT-029
    """
    # given: 5바이트 "a.pdf"
    uploaded = await attachment_env.uploaded(KIM, "a.pdf", b"12345")

    # when: id로 단건을 읽는다
    found = await attachment_env.get.execute(uploaded.id)

    # then: id·이름·크기와 업로더가 올린 값이다
    assert (found.id, found.file_name.value, found.size) == (uploaded.id, "a.pdf", 5)
    assert found.uploaded_by == KIM.user_id


async def test_get_of_an_unknown_id_is_not_found(attachment_env: AttachmentEnv) -> None:
    """없는 id의 단건 조회는 첨부 없음 오류다.

    테스트 코드: AT-029
    """
    # when·then: 없는 id로 읽으면 첨부 없음 오류다
    with raises_with(AttachmentNotFoundError, NOT_FOUND):
        await attachment_env.get.execute(AttachmentId(new_id()))
