"""PartnerMeetingRepository.search 정렬 계약(AC1·4): Fake와 SQL 구현에 같은 기대값.

meeting_date는 (날짜, id)를 방향대로. partner·deal·content·author는 주 키 lower(...)를 방향대로 두고
동률은 방향과 무관하게 미팅 날짜 내림차순 -> id 내림차순이다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest
from app.application.ports.partner_meeting_repository import PartnerMeetingSort

from app.application.ports.deal_repository import SortOrder
from tests.factories_partner_meeting import make_meeting
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.partner_meeting_case import MeetingCase


async def _put(  # noqa: PLR0913 - 미팅 한 건 준비의 독립적인 선택지
    case: MeetingCase,
    code: object,
    content: str,
    day: int,
    *,
    company: str = "한빛파트너스",
    author: object = None,
) -> int:
    kwargs = {} if author is None else {"author": author}
    meeting = await case.add(
        make_meeting(
            deal_code=code,  # type: ignore[arg-type]
            company=company,
            content=content,
            meeting_date=date(2026, 10, day),
            **kwargs,  # type: ignore[arg-type]
        )
    )
    return int(meeting.id)


async def test_the_default_is_meeting_date_descending_then_id_descending(
    meeting_case: MeetingCase,
) -> None:
    code = await meeting_case.deal()
    await _put(meeting_case, code, "10/1 먼저", 1)
    await _put(meeting_case, code, "10/3", 3)
    await _put(meeting_case, code, "10/1 나중", 1)

    assert await meeting_case.contents() == ["10/3", "10/1 나중", "10/1 먼저"]


async def test_meeting_date_ascending_breaks_ties_by_id_ascending(
    meeting_case: MeetingCase,
) -> None:
    code = await meeting_case.deal()
    await _put(meeting_case, code, "10/1 먼저", 1)
    await _put(meeting_case, code, "10/3", 3)
    await _put(meeting_case, code, "10/1 나중", 1)

    assert await meeting_case.contents(order=SortOrder.ASC) == ["10/1 먼저", "10/1 나중", "10/3"]


@pytest.mark.parametrize("order", [SortOrder.ASC, SortOrder.DESC])
async def test_text_sorts_tie_by_date_descending_then_id_descending_regardless_of_order(
    meeting_case: MeetingCase, order: SortOrder
) -> None:
    code = await meeting_case.deal()
    await _put(meeting_case, code, "오래된", 1)
    await _put(meeting_case, code, "최신 먼저", 9)
    await _put(meeting_case, code, "최신 나중", 9)

    found = await meeting_case.contents(sort=PartnerMeetingSort.PARTNER, order=order)

    assert found == ["최신 나중", "최신 먼저", "오래된"]


async def test_the_partner_sort_orders_by_lowercased_company_in_both_directions(
    meeting_case: MeetingCase,
) -> None:
    code = await meeting_case.deal()
    await _put(meeting_case, code, "beta", 1, company="Beta")
    await _put(meeting_case, code, "acme", 2, company="acme")
    await _put(meeting_case, code, "gamma", 3, company="GAMMA")

    ascending = await meeting_case.contents(sort=PartnerMeetingSort.PARTNER, order=SortOrder.ASC)
    descending = await meeting_case.contents(sort=PartnerMeetingSort.PARTNER, order=SortOrder.DESC)

    assert ascending == ["acme", "beta", "gamma"]
    assert descending == ["gamma", "beta", "acme"]


async def test_the_content_sort_orders_by_lowercased_content(meeting_case: MeetingCase) -> None:
    code = await meeting_case.deal()
    await _put(meeting_case, code, "Banana", 1)
    await _put(meeting_case, code, "apple", 2)
    await _put(meeting_case, code, "Cherry", 3)

    found = await meeting_case.contents(sort=PartnerMeetingSort.CONTENT, order=SortOrder.ASC)

    assert found == ["apple", "Banana", "Cherry"]


async def test_the_deal_sort_uses_the_current_deal_name(meeting_case: MeetingCase) -> None:
    alpha = await meeting_case.deal(name="Alpha")
    omega = await meeting_case.deal(name="Omega")
    await _put(meeting_case, alpha, "알파 기록", 1)
    await _put(meeting_case, omega, "오메가 기록", 2)
    assert await meeting_case.contents(sort=PartnerMeetingSort.DEAL, order=SortOrder.ASC) == [
        "알파 기록",
        "오메가 기록",
    ]

    await meeting_case.rename_deal(alpha, "Zulu")

    found = await meeting_case.contents(sort=PartnerMeetingSort.DEAL, order=SortOrder.ASC)
    assert found == ["오메가 기록", "알파 기록"]


async def test_the_author_sort_uses_the_display_name_or_the_login_id_including_resigned(
    meeting_case: MeetingCase,
) -> None:
    code = await meeting_case.deal()
    bravo = await meeting_case.author(uid("sort-a"), "Bravo", login_id="sort-a")
    alpha = await meeting_case.author(uid("sort-b"), None, login_id="alpha")
    charlie = await meeting_case.author(uid("sort-c"), "Charlie", login_id="sort-c")
    await _put(meeting_case, code, "by bravo", 1, author=bravo)
    await _put(meeting_case, code, "by alpha", 2, author=alpha)
    await _put(meeting_case, code, "by charlie", 3, author=charlie)
    await meeting_case.resign(charlie)

    ascending = await meeting_case.contents(sort=PartnerMeetingSort.AUTHOR, order=SortOrder.ASC)
    descending = await meeting_case.contents(sort=PartnerMeetingSort.AUTHOR, order=SortOrder.DESC)

    assert ascending == ["by alpha", "by bravo", "by charlie"]
    assert descending == ["by charlie", "by bravo", "by alpha"]


async def test_paging_follows_the_sort_order(meeting_case: MeetingCase) -> None:
    code = await meeting_case.deal()
    for day in range(1, 6):
        await _put(meeting_case, code, f"d{day}", day)

    page = await meeting_case.contents(offset=2, limit=2)

    assert page == ["d3", "d2"]
