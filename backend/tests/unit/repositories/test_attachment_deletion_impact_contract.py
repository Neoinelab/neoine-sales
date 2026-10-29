"""DealRepository.deletion_impact의 첨부 건수(P2b AC-15): Fake와 SQL에 같은 기대값."""

from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealDeletionImpact
from tests.factories import make_deal_code
from tests.factories_attachment import make_attachment

if TYPE_CHECKING:
    from tests.unit.repositories.attachment_case import AttachmentCase

DEAL = make_deal_code("A001")
OTHER = make_deal_code("A002")


async def test_a_deal_without_attachments_counts_zero(attachment_case: AttachmentCase) -> None:
    await attachment_case.ensure_deal(DEAL)

    impact = await attachment_case.deals.deletion_impact(DEAL)

    assert impact == DealDeletionImpact(
        history_count=0, action_count=0, attachment_count=0, partner_meeting_count=0
    )


async def test_each_attachment_of_the_deal_is_counted_once(attachment_case: AttachmentCase) -> None:
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        await attachment_case.add(make_attachment(deal_code=DEAL, name=name))

    impact = await attachment_case.deals.deletion_impact(DEAL)

    assert impact.attachment_count == 3


async def test_other_deals_attachments_are_not_counted(attachment_case: AttachmentCase) -> None:
    await attachment_case.add(make_attachment(deal_code=DEAL, name="a.pdf"))
    await attachment_case.add(make_attachment(deal_code=OTHER, name="b.pdf"))
    await attachment_case.add(make_attachment(deal_code=OTHER, name="c.pdf"))

    assert (await attachment_case.deals.deletion_impact(DEAL)).attachment_count == 1
    assert (await attachment_case.deals.deletion_impact(OTHER)).attachment_count == 2


async def test_the_count_is_what_a_delete_would_remove(attachment_case: AttachmentCase) -> None:
    attachment = make_attachment(deal_code=DEAL)
    await attachment_case.add(attachment)
    impact = await attachment_case.deals.deletion_impact(DEAL)

    await attachment_case.deals.delete(DEAL)

    assert impact.attachment_count == 1
    assert await attachment_case.names(DEAL) == []


async def test_a_deleted_attachment_is_no_longer_counted(attachment_case: AttachmentCase) -> None:
    attachment = make_attachment(deal_code=DEAL)
    await attachment_case.add(attachment)

    await attachment_case.repository.delete(attachment.id)

    assert (await attachment_case.deals.deletion_impact(DEAL)).attachment_count == 0
