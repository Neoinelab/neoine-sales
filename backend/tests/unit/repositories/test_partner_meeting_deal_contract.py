"""Deal 삭제와 미팅 기록(AC18, D6): CASCADE 삭제와 삭제 영향 건수. Fake와 SQL 구현에 같은 기대값."""

from typing import TYPE_CHECKING

import pytest
from app.domain.partner_meeting.errors import PartnerMeetingNotFoundError

from app.application.ports.deal_repository import DealDeletionImpact

if TYPE_CHECKING:
    from tests.unit.repositories.partner_meeting_case import MeetingCase


async def test_delete_deal_cascades_partner_meetings_and_keeps_other_deals(
    meeting_case: MeetingCase,
) -> None:
    doomed = await meeting_case.deal(name="지울 Deal")
    kept = await meeting_case.deal(name="남길 Deal")
    gone_one, gone_two = await meeting_case.add_many(doomed, "삭제 1", "삭제 2")
    (survivor,) = await meeting_case.add_many(kept, "생존")

    await meeting_case.deals.delete(doomed)

    for meeting in (gone_one, gone_two):
        with pytest.raises(PartnerMeetingNotFoundError):
            await meeting_case.repository.get(meeting.id)
    assert await meeting_case.contents() == ["생존"]
    assert (await meeting_case.repository.get(survivor.id)).meeting.content.value == "생존"
    assert await meeting_case.total() == 1


async def test_deleting_a_deal_does_not_delete_the_contacts_or_the_author(
    meeting_case: MeetingCase,
) -> None:
    partner = await meeting_case.partner()
    code = await meeting_case.deal(partner=partner)
    (meeting,) = await meeting_case.add_many(code, "기록")

    await meeting_case.deals.delete(code)

    assert (await meeting_case.contacts.get(partner.id)).id == partner.id
    assert (await meeting_case.users.get(meeting.author_user_id)).id == meeting.author_user_id


async def test_deletion_impact_counts_the_partner_meetings_of_that_deal_only(
    meeting_case: MeetingCase,
) -> None:
    first = await meeting_case.deal()
    second = await meeting_case.deal()
    await meeting_case.add_many(first, "a", "b", "c")
    await meeting_case.add_many(second, "d")

    first_impact = await meeting_case.deals.deletion_impact(first)
    second_impact = await meeting_case.deals.deletion_impact(second)

    assert first_impact.partner_meeting_count == 3
    assert second_impact.partner_meeting_count == 1


async def test_deletion_impact_of_a_deal_without_meetings_is_zero(
    meeting_case: MeetingCase,
) -> None:
    code = await meeting_case.deal()

    impact = await meeting_case.deals.deletion_impact(code)

    assert impact.partner_meeting_count == 0
    assert isinstance(impact, DealDeletionImpact)


async def test_deleting_a_meeting_lowers_the_deletion_impact(meeting_case: MeetingCase) -> None:
    code = await meeting_case.deal()
    first, _second = await meeting_case.add_many(code, "a", "b")

    await meeting_case.repository.delete(first.id)

    assert (await meeting_case.deals.deletion_impact(code)).partner_meeting_count == 1
