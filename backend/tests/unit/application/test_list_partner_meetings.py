"""ListPartnerMeetings(AC1·2·3): 한 UoW에서 페이지와 전체 건수를 함께 읽는다."""

from datetime import date
from typing import TYPE_CHECKING

from app.application.ports.partner_meeting_repository import PartnerMeetingQuery

from tests.unit.application.partner_meeting_env import HANBIT, KIM, PARK

if TYPE_CHECKING:
    from tests.unit.application.partner_meeting_env import MeetingEnv


async def _twelve(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal()
    for day in range(1, 13):
        await meeting_env.register_one(
            KIM, code, meeting_date=date(2026, 10, day), content=f"{day}"
        )


async def test_the_first_page_has_ten_items_and_the_total_counts_all(
    meeting_env: MeetingEnv,
) -> None:
    await _twelve(meeting_env)

    page = await meeting_env.list.execute(PartnerMeetingQuery())

    assert (len(page.items), page.total, page.offset, page.limit) == (10, 12, 0, 10)
    assert [r.meeting.content.value for r in page.items][:2] == ["12", "11"]


async def test_the_next_page_continues_where_the_first_stopped(meeting_env: MeetingEnv) -> None:
    await _twelve(meeting_env)

    page = await meeting_env.list.execute(PartnerMeetingQuery(offset=10))

    assert [r.meeting.content.value for r in page.items] == ["2", "1"]
    assert (page.total, page.offset, page.limit) == (12, 10, 10)


async def test_the_total_follows_the_filters_not_the_page(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal()
    await meeting_env.register_one(KIM, code, content="견적 논의")
    await meeting_env.register_one(PARK, code, content="계약 논의")
    await meeting_env.register_one(KIM, code, content="기타")

    page = await meeting_env.list.execute(PartnerMeetingQuery(content="논의", limit=1))

    assert (len(page.items), page.total) == (1, 2)


async def test_no_records_gives_an_empty_page_with_zero_total(meeting_env: MeetingEnv) -> None:
    page = await meeting_env.list.execute(PartnerMeetingQuery())

    assert list(page.items) == []
    assert page.total == 0


async def test_each_item_carries_the_current_deal_name(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal(name="ERP 구축")
    await meeting_env.register_one(KIM, code, company=HANBIT)

    page = await meeting_env.list.execute(PartnerMeetingQuery())

    assert [r.deal_name for r in page.items] == ["ERP 구축"]
