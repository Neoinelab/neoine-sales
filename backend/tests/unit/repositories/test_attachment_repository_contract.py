"""AttachmentRepository 계약: 저장·조회·이름 중복·정렬·수정·삭제, Fake와 SQL 공통."""

from typing import TYPE_CHECKING

import pytest

from app.domain.attachment.errors import AttachmentNameTakenError, AttachmentNotFoundError
from app.domain.attachment.values import MAX_FILE_BYTES, AttachmentId, FileName
from app.domain.deal.errors import DealNotFoundError
from tests.factories import later, make_deal_code
from tests.factories_attachment import make_attachment
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.support.user_ids import uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from tests.unit.repositories.attachment_case import AttachmentCase

DEAL = make_deal_code("A001")
OTHER_DEAL = make_deal_code("A002")


async def test_add_then_get_round_trips_every_field(attachment_case: AttachmentCase) -> None:
    """첨부를 저장하고 읽으면 모든 필드가 그대로 돌아온다."""
    # given: 모든 필드를 채운 첨부
    attachment = make_attachment(
        later(5),
        deal_code=DEAL,
        name="견적서 😀.pdf",
        description=" ".join(["최종"] * 20),
        size=1_234,
        mime="application/pdf",
        storage_key="ab" * 16,
        uploaded_by=uid("kim"),
    )
    # when: 첨부를 저장하고 id로 읽는다
    await attachment_case.add(attachment)

    stored = await attachment_case.repository.get(attachment.id)

    # then: 읽은 첨부의 모든 필드가 저장한 값과 같다
    assert stored.id == attachment.id
    assert stored.deal_code == DEAL
    assert stored.file_name == FileName.parse("견적서 😀.pdf")
    assert stored.description == " ".join(["최종"] * 20)
    assert (stored.size, stored.mime, stored.storage_key) == (1_234, "application/pdf", "ab" * 16)
    assert stored.uploaded_by == uid("kim")
    assert stored.uploaded_at == stored.created_at == stored.updated_at == later(5)


@pytest.mark.parametrize("size", [0, 1, MAX_FILE_BYTES])
async def test_the_size_boundaries_are_stored(attachment_case: AttachmentCase, size: int) -> None:
    """0·1·100MB 크기가 그대로 저장된다."""
    # given: 경계 크기의 첨부
    attachment = make_attachment(deal_code=DEAL, size=size)
    # when: 저장하고 읽는다
    await attachment_case.add(attachment)

    # then: 읽은 크기가 저장한 크기와 같다
    assert (await attachment_case.repository.get(attachment.id)).size == size


async def test_get_of_an_unknown_id_raises_not_found(attachment_case: AttachmentCase) -> None:
    """없는 id를 읽으면 첨부 없음 오류다."""
    # when·then: 없는 id를 읽으면 "첨부 파일을 찾을 수 없습니다." 오류다
    with raises_with(AttachmentNotFoundError, "첨부 파일을 찾을 수 없습니다."):
        await attachment_case.repository.get(AttachmentId(new_id()))


async def test_add_for_a_missing_deal_raises_deal_not_found_and_the_repository_stays_usable(
    attachment_case: AttachmentCase,
) -> None:
    """없는 Deal에 저장하면 Deal 없음 오류이고 저장소는 계속 쓸 수 있다."""
    # given: 사용자가 있고 없는 Deal의 첨부를 준비한다
    await ensure_users(attachment_case.users, uid("kim"))
    ghost = make_attachment(deal_code=make_deal_code("ZZZZ"), uploaded_by=uid("kim"))

    # when: 없는 Deal의 첨부를 저장한다
    with pytest.raises(DealNotFoundError):
        await attachment_case.repository.add(ghost)

    # then: Deal 없음 오류가 난다
    later_one = make_attachment(deal_code=DEAL, uploaded_by=uid("kim"))
    # when: 이어서 올바른 첨부를 저장한다
    await attachment_case.add(later_one)
    # then: 그 첨부를 읽을 수 있다
    assert (await attachment_case.repository.get(later_one.id)).id == later_one.id


async def test_the_same_name_in_the_same_deal_raises_name_taken_and_keeps_the_first(
    attachment_case: AttachmentCase,
) -> None:
    """같은 Deal의 같은 이름은 충돌 오류이고 먼저 저장한 첨부가 남는다."""
    # given: "a.pdf"가 저장되어 있다
    first = make_attachment(deal_code=DEAL, name="a.pdf", size=1)
    await attachment_case.add(first)

    # when·then: 같은 이름을 또 저장하면 같은 이름 오류다
    with raises_with(AttachmentNameTakenError, "같은 이름의 파일이 이미 있습니다: a.pdf"):
        await attachment_case.add(make_attachment(deal_code=DEAL, name="a.pdf", size=2))

    # then: 목록과 첫 첨부의 크기가 그대로다
    assert [a.id for a in await attachment_case.repository.list_by_deal(DEAL)] == [first.id]
    assert (await attachment_case.repository.get(first.id)).size == 1


async def test_after_a_name_conflict_the_transaction_is_still_usable(
    attachment_case: AttachmentCase,
) -> None:
    """이름 충돌 뒤에도 같은 트랜잭션을 계속 쓸 수 있다."""
    # given: "a.pdf"가 저장되어 있고 같은 이름 저장이 충돌했다
    await attachment_case.add(make_attachment(deal_code=DEAL, name="a.pdf"))
    with pytest.raises(AttachmentNameTakenError):
        await attachment_case.add(make_attachment(deal_code=DEAL, name="a.pdf"))

    # when: 다른 이름을 저장한다
    fresh = make_attachment(deal_code=DEAL, name="b.pdf")
    await attachment_case.add(fresh)

    # then: 두 이름이 모두 목록에 있다
    assert sorted(await attachment_case.names(DEAL)) == ["a.pdf", "b.pdf"]


async def test_names_that_differ_only_by_case_are_separate_files(
    attachment_case: AttachmentCase,
) -> None:
    """대소문자만 다른 이름은 별개 파일로 저장된다."""
    # when: "Report.PDF"와 "report.pdf"를 저장한다
    await attachment_case.add(make_attachment(deal_code=DEAL, name="Report.PDF"))
    await attachment_case.add(make_attachment(deal_code=DEAL, name="report.pdf"))

    # then: 두 이름이 모두 있다
    assert sorted(await attachment_case.names(DEAL)) == ["Report.PDF", "report.pdf"]


async def test_the_same_name_in_another_deal_is_allowed(attachment_case: AttachmentCase) -> None:
    """다른 Deal의 같은 이름은 허용된다."""
    # given: Deal 하나에 "a.pdf"가 있다
    await attachment_case.add(make_attachment(deal_code=DEAL, name="a.pdf"))

    # when: 다른 Deal에 같은 이름을 저장한다
    await attachment_case.add(make_attachment(deal_code=OTHER_DEAL, name="a.pdf"))

    # then: 두 Deal 모두 "a.pdf"를 가진다
    assert await attachment_case.names(DEAL) == ["a.pdf"]
    assert await attachment_case.names(OTHER_DEAL) == ["a.pdf"]


async def test_find_by_name_returns_the_exact_match_only(attachment_case: AttachmentCase) -> None:
    """이름 조회는 글자가 정확히 같은 첨부만 돌려준다."""
    # given: 한 Deal의 "Report.pdf"와 다른 Deal
    attachment = make_attachment(deal_code=DEAL, name="Report.pdf")
    await attachment_case.add(attachment)
    await attachment_case.ensure_deal(OTHER_DEAL)
    repository = attachment_case.repository

    # when: 이름으로 찾는다
    found = await repository.find_by_name(DEAL, FileName.parse("Report.pdf"))

    # then: 정확히 같은 이름만 찾고 대소문자가 다르거나 다른 Deal·없는 이름은 None이다
    assert found is not None
    assert found.id == attachment.id
    assert await repository.find_by_name(DEAL, FileName.parse("report.pdf")) is None
    assert await repository.find_by_name(OTHER_DEAL, FileName.parse("Report.pdf")) is None
    assert await repository.find_by_name(DEAL, FileName.parse("none.pdf")) is None


async def test_list_by_deal_is_newest_upload_first(attachment_case: AttachmentCase) -> None:
    """목록은 최신 업로드 순이다."""
    # given: 시각이 다른 세 첨부를 저장한다
    for seconds, name in ((10, "old.pdf"), (30, "new.pdf"), (20, "middle.pdf")):
        await attachment_case.add(make_attachment(later(seconds), deal_code=DEAL, name=name))

    # when: 이름 목록을 읽는다
    names = await attachment_case.names(DEAL)

    # then: 최신 순서로 나온다
    assert names == ["new.pdf", "middle.pdf", "old.pdf"]


async def test_list_by_deal_breaks_ties_by_id_descending(attachment_case: AttachmentCase) -> None:
    """같은 시각이면 id 내림차순이다."""
    # given: 같은 시각의 첨부 다섯 건
    ids = [AttachmentId(new_id()) for _ in range(5)]
    for number, attachment_id in enumerate(ids):
        attachment = make_attachment(
            later(1), deal_code=DEAL, name=f"{number}.pdf", entity_id=attachment_id
        )
        await attachment_case.add(attachment)

    # when: 목록을 읽는다
    found = await attachment_case.repository.list_by_deal(DEAL)

    # then: id 내림차순이다
    assert [a.id for a in found] == sorted(ids, reverse=True)


async def test_list_by_deal_returns_only_that_deals_files(attachment_case: AttachmentCase) -> None:
    """목록은 그 Deal의 파일만 돌려준다."""
    # given: 두 Deal에 각각 파일이 있다
    await attachment_case.add(make_attachment(deal_code=DEAL, name="mine.pdf"))
    await attachment_case.add(make_attachment(deal_code=OTHER_DEAL, name="theirs.pdf"))

    # when: 이 Deal의 이름 목록을 읽는다
    names = await attachment_case.names(DEAL)

    # then: 이 Deal의 파일만 나온다
    assert names == ["mine.pdf"]


async def test_list_by_deal_of_a_deal_without_files_is_empty(
    attachment_case: AttachmentCase,
) -> None:
    """파일이 없는 Deal의 목록은 비어 있다."""
    # given: 파일이 없는 Deal
    await attachment_case.ensure_deal(DEAL)

    # when: 목록을 읽는다
    found = list(await attachment_case.repository.list_by_deal(DEAL))

    # then: 목록이 비어 있다
    assert found == []


async def test_update_stores_the_replacement_fields_and_keeps_the_identity(
    attachment_case: AttachmentCase,
) -> None:
    """수정하면 교체 필드가 저장되고 id·이름·Deal·생성 시각은 그대로다."""
    # given: 저장된 첨부와 새 업로더
    attachment = make_attachment(later(1), deal_code=DEAL, name="a.pdf", uploaded_by=uid("kim"))
    await attachment_case.add(attachment)
    await ensure_users(attachment_case.users, uid("boss"))
    attachment.replace(
        description="새 설명",
        size=777,
        mime="text/plain",
        storage_key="cd" * 16,
        uploaded_by=uid("boss"),
        now=later(90),
    )

    # when: 교체한 첨부를 저장소에 반영한다
    await attachment_case.repository.update(attachment)

    # then: 교체 필드가 새 값이고 생성 시각·이름·Deal은 그대로다
    stored = await attachment_case.repository.get(attachment.id)
    assert (stored.description, stored.size, stored.mime) == ("새 설명", 777, "text/plain")
    assert (stored.storage_key, stored.uploaded_by) == ("cd" * 16, uid("boss"))
    assert stored.uploaded_at == stored.updated_at == later(90)
    assert stored.created_at == later(1)
    assert (stored.deal_code, stored.file_name) == (DEAL, FileName.parse("a.pdf"))


async def test_update_does_not_touch_other_files(attachment_case: AttachmentCase) -> None:
    """수정은 다른 파일을 건드리지 않는다."""
    # given: 같은 Deal의 두 첨부
    changed = make_attachment(deal_code=DEAL, name="a.pdf", size=1)
    untouched = make_attachment(deal_code=DEAL, name="b.pdf", size=2)
    await attachment_case.add(changed)
    await attachment_case.add(untouched)
    changed.replace(
        description="x",
        size=9,
        mime="a/b",
        storage_key="ef" * 16,
        uploaded_by=changed.uploaded_by,
        now=later(5),
    )

    # when: 한 첨부만 교체해 반영한다
    await attachment_case.repository.update(changed)

    # then: 다른 첨부의 크기가 그대로다
    assert (await attachment_case.repository.get(untouched.id)).size == 2


async def test_update_of_an_unknown_attachment_raises_not_found(
    attachment_case: AttachmentCase,
) -> None:
    """없는 첨부를 수정하면 첨부 없음 오류다."""
    # given: Deal만 있다
    await attachment_case.ensure_deal(DEAL)

    # when·then: 저장하지 않은 첨부를 수정하면 첨부 없음 오류다
    with pytest.raises(AttachmentNotFoundError):
        await attachment_case.repository.update(make_attachment(deal_code=DEAL))


async def test_delete_removes_only_that_attachment(attachment_case: AttachmentCase) -> None:
    """삭제는 그 첨부만 지운다."""
    # given: 같은 Deal의 두 첨부
    gone = make_attachment(deal_code=DEAL, name="gone.pdf")
    kept = make_attachment(deal_code=DEAL, name="kept.pdf")
    await attachment_case.add(gone)
    await attachment_case.add(kept)

    # when: 한 첨부를 지운다
    await attachment_case.repository.delete(gone.id)

    # then: 지운 첨부는 읽히지 않고 다른 첨부만 남는다
    with pytest.raises(AttachmentNotFoundError):
        await attachment_case.repository.get(gone.id)
    assert await attachment_case.names(DEAL) == ["kept.pdf"]


async def test_a_deleted_name_can_be_used_again(attachment_case: AttachmentCase) -> None:
    """지운 이름은 다시 쓸 수 있다."""
    # given: 저장했다가 지운 "a.pdf"
    first = make_attachment(deal_code=DEAL, name="a.pdf")
    await attachment_case.add(first)
    await attachment_case.repository.delete(first.id)

    # when: 같은 이름을 다시 저장한다
    again = make_attachment(deal_code=DEAL, name="a.pdf")
    await attachment_case.add(again)

    # then: 새 첨부를 읽을 수 있다
    assert (await attachment_case.repository.get(again.id)).id == again.id


async def test_delete_of_an_unknown_attachment_raises_not_found(
    attachment_case: AttachmentCase,
) -> None:
    """없는 id를 지우면 첨부 없음 오류다."""
    # when·then: 없는 id를 지우면 첨부 없음 오류다
    with pytest.raises(AttachmentNotFoundError):
        await attachment_case.repository.delete(AttachmentId(new_id()))


async def test_deleting_a_deal_deletes_its_attachments_and_only_its_own(
    attachment_case: AttachmentCase,
) -> None:
    """Deal을 지우면 그 Deal의 첨부만 함께 지워진다."""
    # given: 두 Deal에 각각 첨부가 있다
    mine = make_attachment(deal_code=DEAL, name="mine.pdf")
    theirs = make_attachment(deal_code=OTHER_DEAL, name="theirs.pdf")
    await attachment_case.add(mine)
    await attachment_case.add(theirs)

    # when: 한 Deal을 지운다
    await attachment_case.deals.delete(DEAL)

    # then: 그 Deal의 첨부는 읽히지 않고 다른 Deal의 첨부는 남는다
    with pytest.raises(AttachmentNotFoundError):
        await attachment_case.repository.get(mine.id)
    assert await attachment_case.names(OTHER_DEAL) == ["theirs.pdf"]
