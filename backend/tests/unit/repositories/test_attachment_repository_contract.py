"""AttachmentRepository 계약(P2b R2): 저장·조회·이름 중복·정렬·수정·삭제, Fake와 SQL 공통."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.domain.attachment.errors import AttachmentNameTakenError, AttachmentNotFoundError
from app.domain.attachment.values import MAX_FILE_BYTES, AttachmentId, FileName
from app.domain.deal.errors import DealNotFoundError
from tests.factories import later, make_deal_code
from tests.factories_attachment import make_attachment
from tests.support.expect import raises_with
from tests.support.user_ids import uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from tests.unit.repositories.attachment_case import AttachmentCase

DEAL = make_deal_code("A001")
OTHER_DEAL = make_deal_code("A002")


async def test_add_then_get_round_trips_every_field(attachment_case: AttachmentCase) -> None:
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
    await attachment_case.add(attachment)

    stored = await attachment_case.repository.get(attachment.id)

    assert stored.id == attachment.id
    assert stored.deal_code == DEAL
    assert stored.file_name == FileName.parse("견적서 😀.pdf")
    assert stored.description == " ".join(["최종"] * 20)
    assert (stored.size, stored.mime, stored.storage_key) == (1_234, "application/pdf", "ab" * 16)
    assert stored.uploaded_by == uid("kim")
    assert stored.uploaded_at == stored.created_at == stored.updated_at == later(5)


@pytest.mark.parametrize("size", [0, 1, MAX_FILE_BYTES])
async def test_the_size_boundaries_are_stored(attachment_case: AttachmentCase, size: int) -> None:
    attachment = make_attachment(deal_code=DEAL, size=size)
    await attachment_case.add(attachment)

    assert (await attachment_case.repository.get(attachment.id)).size == size


async def test_get_of_an_unknown_id_raises_not_found(attachment_case: AttachmentCase) -> None:
    with raises_with(AttachmentNotFoundError, "첨부 파일을 찾을 수 없습니다."):
        await attachment_case.repository.get(AttachmentId(uuid4()))


async def test_add_for_a_missing_deal_raises_deal_not_found_and_the_repository_stays_usable(
    attachment_case: AttachmentCase,
) -> None:
    await ensure_users(attachment_case.users, uid("kim"))
    ghost = make_attachment(deal_code=make_deal_code("ZZZZ"), uploaded_by=uid("kim"))

    with pytest.raises(DealNotFoundError):
        await attachment_case.repository.add(ghost)

    later_one = make_attachment(deal_code=DEAL, uploaded_by=uid("kim"))
    await attachment_case.add(later_one)
    assert (await attachment_case.repository.get(later_one.id)).id == later_one.id


async def test_the_same_name_in_the_same_deal_raises_name_taken_and_keeps_the_first(
    attachment_case: AttachmentCase,
) -> None:
    first = make_attachment(deal_code=DEAL, name="a.pdf", size=1)
    await attachment_case.add(first)

    with raises_with(AttachmentNameTakenError, "같은 이름의 파일이 이미 있습니다: a.pdf"):
        await attachment_case.add(make_attachment(deal_code=DEAL, name="a.pdf", size=2))

    assert [a.id for a in await attachment_case.repository.list_by_deal(DEAL)] == [first.id]
    assert (await attachment_case.repository.get(first.id)).size == 1


async def test_after_a_name_conflict_the_transaction_is_still_usable(
    attachment_case: AttachmentCase,
) -> None:
    await attachment_case.add(make_attachment(deal_code=DEAL, name="a.pdf"))
    with pytest.raises(AttachmentNameTakenError):
        await attachment_case.add(make_attachment(deal_code=DEAL, name="a.pdf"))

    fresh = make_attachment(deal_code=DEAL, name="b.pdf")
    await attachment_case.add(fresh)

    assert sorted(await attachment_case.names(DEAL)) == ["a.pdf", "b.pdf"]


async def test_names_that_differ_only_by_case_are_separate_files(
    attachment_case: AttachmentCase,
) -> None:
    await attachment_case.add(make_attachment(deal_code=DEAL, name="Report.PDF"))
    await attachment_case.add(make_attachment(deal_code=DEAL, name="report.pdf"))

    assert sorted(await attachment_case.names(DEAL)) == ["Report.PDF", "report.pdf"]


async def test_the_same_name_in_another_deal_is_allowed(attachment_case: AttachmentCase) -> None:
    await attachment_case.add(make_attachment(deal_code=DEAL, name="a.pdf"))

    await attachment_case.add(make_attachment(deal_code=OTHER_DEAL, name="a.pdf"))

    assert await attachment_case.names(DEAL) == ["a.pdf"]
    assert await attachment_case.names(OTHER_DEAL) == ["a.pdf"]


async def test_find_by_name_returns_the_exact_match_only(attachment_case: AttachmentCase) -> None:
    attachment = make_attachment(deal_code=DEAL, name="Report.pdf")
    await attachment_case.add(attachment)
    await attachment_case.ensure_deal(OTHER_DEAL)
    repository = attachment_case.repository

    found = await repository.find_by_name(DEAL, FileName.parse("Report.pdf"))

    assert found is not None
    assert found.id == attachment.id
    assert await repository.find_by_name(DEAL, FileName.parse("report.pdf")) is None
    assert await repository.find_by_name(OTHER_DEAL, FileName.parse("Report.pdf")) is None
    assert await repository.find_by_name(DEAL, FileName.parse("none.pdf")) is None


async def test_list_by_deal_is_newest_upload_first(attachment_case: AttachmentCase) -> None:
    for seconds, name in ((10, "old.pdf"), (30, "new.pdf"), (20, "middle.pdf")):
        await attachment_case.add(make_attachment(later(seconds), deal_code=DEAL, name=name))

    assert await attachment_case.names(DEAL) == ["new.pdf", "middle.pdf", "old.pdf"]


async def test_list_by_deal_breaks_ties_by_id_descending(attachment_case: AttachmentCase) -> None:
    ids = [AttachmentId(uuid4()) for _ in range(5)]
    for number, attachment_id in enumerate(ids):
        attachment = make_attachment(
            later(1), deal_code=DEAL, name=f"{number}.pdf", entity_id=attachment_id
        )
        await attachment_case.add(attachment)

    found = await attachment_case.repository.list_by_deal(DEAL)

    assert [a.id for a in found] == sorted(ids, key=str, reverse=True)


async def test_list_by_deal_returns_only_that_deals_files(attachment_case: AttachmentCase) -> None:
    await attachment_case.add(make_attachment(deal_code=DEAL, name="mine.pdf"))
    await attachment_case.add(make_attachment(deal_code=OTHER_DEAL, name="theirs.pdf"))

    assert await attachment_case.names(DEAL) == ["mine.pdf"]


async def test_list_by_deal_of_a_deal_without_files_is_empty(
    attachment_case: AttachmentCase,
) -> None:
    await attachment_case.ensure_deal(DEAL)

    assert list(await attachment_case.repository.list_by_deal(DEAL)) == []


async def test_update_stores_the_replacement_fields_and_keeps_the_identity(
    attachment_case: AttachmentCase,
) -> None:
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

    await attachment_case.repository.update(attachment)

    stored = await attachment_case.repository.get(attachment.id)
    assert (stored.description, stored.size, stored.mime) == ("새 설명", 777, "text/plain")
    assert (stored.storage_key, stored.uploaded_by) == ("cd" * 16, uid("boss"))
    assert stored.uploaded_at == stored.updated_at == later(90)
    assert stored.created_at == later(1)
    assert (stored.deal_code, stored.file_name) == (DEAL, FileName.parse("a.pdf"))


async def test_update_does_not_touch_other_files(attachment_case: AttachmentCase) -> None:
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

    await attachment_case.repository.update(changed)

    assert (await attachment_case.repository.get(untouched.id)).size == 2


async def test_update_of_an_unknown_attachment_raises_not_found(
    attachment_case: AttachmentCase,
) -> None:
    await attachment_case.ensure_deal(DEAL)

    with pytest.raises(AttachmentNotFoundError):
        await attachment_case.repository.update(make_attachment(deal_code=DEAL))


async def test_delete_removes_only_that_attachment(attachment_case: AttachmentCase) -> None:
    gone = make_attachment(deal_code=DEAL, name="gone.pdf")
    kept = make_attachment(deal_code=DEAL, name="kept.pdf")
    await attachment_case.add(gone)
    await attachment_case.add(kept)

    await attachment_case.repository.delete(gone.id)

    with pytest.raises(AttachmentNotFoundError):
        await attachment_case.repository.get(gone.id)
    assert await attachment_case.names(DEAL) == ["kept.pdf"]


async def test_a_deleted_name_can_be_used_again(attachment_case: AttachmentCase) -> None:
    first = make_attachment(deal_code=DEAL, name="a.pdf")
    await attachment_case.add(first)
    await attachment_case.repository.delete(first.id)

    again = make_attachment(deal_code=DEAL, name="a.pdf")
    await attachment_case.add(again)

    assert (await attachment_case.repository.get(again.id)).id == again.id


async def test_delete_of_an_unknown_attachment_raises_not_found(
    attachment_case: AttachmentCase,
) -> None:
    with pytest.raises(AttachmentNotFoundError):
        await attachment_case.repository.delete(AttachmentId(uuid4()))


async def test_deleting_a_deal_deletes_its_attachments_and_only_its_own(
    attachment_case: AttachmentCase,
) -> None:
    mine = make_attachment(deal_code=DEAL, name="mine.pdf")
    theirs = make_attachment(deal_code=OTHER_DEAL, name="theirs.pdf")
    await attachment_case.add(mine)
    await attachment_case.add(theirs)

    await attachment_case.deals.delete(DEAL)

    with pytest.raises(AttachmentNotFoundError):
        await attachment_case.repository.get(mine.id)
    assert await attachment_case.names(OTHER_DEAL) == ["theirs.pdf"]
