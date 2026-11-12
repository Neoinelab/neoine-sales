"""ListPartnerMeetings: 한 UoW에서 페이지와 전체 건수를 함께 읽는다."""

from datetime import date
from typing import TYPE_CHECKING

from app.application.ports.partner_meeting_repository import PartnerMeetingQuery
from tests.unit.application.partner_meeting_env import HANBIT, KIM, PARK

if TYPE_CHECKING:
    from tests.unit.application.partner_meeting_env import MeetingEnv


async def _twelve(meeting_env: MeetingEnv) -> None:
    await meeting_env.partner(HANBIT)
    for day in range(1, 13):
        await meeting_env.register_one(KIM, meeting_date=date(2026, 10, day), content=f"{day}")


async def test_the_first_page_has_ten_items_and_the_total_counts_all(
    meeting_env: MeetingEnv,
) -> None:
    """기본 목록은 미팅 날짜 최신순 10건과 전체 건수다.

    테스트 코드: PA-013
    """
    # given: 날짜가 서로 다른 12건
    await _twelve(meeting_env)
    # when: 조건 없이 읽는다
    page = await meeting_env.list.execute(PartnerMeetingQuery())
    # then: 가장 늦은 10건이 내림차순이고 total 12, offset 0, limit 10이다
    assert (len(page.items), page.total, page.offset, page.limit) == (10, 12, 0, 10)
    assert [m.content.value for m in page.items][:2] == ["12", "11"]


async def test_the_next_page_continues_where_the_first_stopped(meeting_env: MeetingEnv) -> None:
    """offset으로 다음 쪽이 겹침 없이 이어진다.

    테스트 코드: PA-014
    """
    # given: 날짜가 서로 다른 12건
    await _twelve(meeting_env)
    # when: offset 10으로 읽는다
    page = await meeting_env.list.execute(PartnerMeetingQuery(offset=10))
    # then: 나머지 2건이 이어지는 순서로 온다
    assert [m.content.value for m in page.items] == ["2", "1"]
    assert (page.total, page.offset, page.limit) == (12, 10, 10)


async def test_the_total_follows_the_filters_not_the_page(meeting_env: MeetingEnv) -> None:
    """전체 건수는 페이지가 아니라 조건을 따른다.

    테스트 코드: PA-026
    """
    # given: "논의"가 든 기록 둘과 아닌 기록 하나
    await meeting_env.partner(HANBIT)
    await meeting_env.register_one(KIM, content="견적 논의")
    await meeting_env.register_one(PARK, content="계약 논의")
    await meeting_env.register_one(KIM, content="기타")
    # when: 내용 "논의", limit 1로 읽는다
    page = await meeting_env.list.execute(PartnerMeetingQuery(content="논의", limit=1))
    # then: 1건이 오고 전체 건수는 2다
    assert (len(page.items), page.total) == (1, 2)


async def test_no_records_gives_an_empty_page_with_zero_total(meeting_env: MeetingEnv) -> None:
    """기록이 없으면 빈 쪽과 0건이다.

    테스트 코드: PA-020
    """
    # when: 기록이 없을 때 읽는다
    page = await meeting_env.list.execute(PartnerMeetingQuery())
    # then: 빈 목록과 total 0이다
    assert list(page.items) == []
    assert page.total == 0


async def test_each_item_is_the_meeting_itself_with_company_and_author(
    meeting_env: MeetingEnv,
) -> None:
    """목록 항목은 기록 자체이고 회사와 작성자를 갖는다."""
    # given: KIM의 기록 한 건
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM, company=HANBIT)
    # when: 목록을 읽는다
    page = await meeting_env.list.execute(PartnerMeetingQuery())
    # then: 항목은 그 기록의 id·회사·작성자다
    assert [(m.id, m.partner_company, m.author_user_id) for m in page.items] == [
        (created.id, HANBIT, KIM.user_id)
    ]
