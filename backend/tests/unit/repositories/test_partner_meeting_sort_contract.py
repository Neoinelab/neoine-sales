"""PartnerMeetingRepository.search 정렬 계약: Fake와 SQL 구현에 같은 기대값.

meeting_date는 (날짜, id)를 방향대로. partner·content·author는 주 키 lower(...)를 방향대로 두고
동률은 방향과 무관하게 미팅 날짜 내림차순 -> id 내림차순이다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import SortOrder
from app.application.ports.partner_meeting_repository import PartnerMeetingSort
from tests.factories_partner_meeting import make_meeting
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.partner_meeting_case import MeetingCase


async def _put(
    case: MeetingCase,
    content: str,
    day: int,
    *,
    company: str = "한빛파트너스",
    author: object = None,
) -> int:
    kwargs = {} if author is None else {"author": author}
    meeting = await case.add(
        make_meeting(
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
    """기본 정렬은 미팅 날짜 내림차순이고 같은 날은 나중에 등록한 것이 먼저다.

    테스트 코드: PA-013, PA-015
    """
    # given: 10/1 두 건(먼저·나중)과 10/3 한 건
    await _put(meeting_case, "10/1 먼저", 1)
    await _put(meeting_case, "10/3", 3)
    await _put(meeting_case, "10/1 나중", 1)
    # when: 기본 정렬로 읽는다
    found = await meeting_case.contents()
    # then: 10/3, 10/1 나중, 10/1 먼저 순이다
    assert found == ["10/3", "10/1 나중", "10/1 먼저"]


async def test_meeting_date_ascending_breaks_ties_by_id_ascending(
    meeting_case: MeetingCase,
) -> None:
    """order=asc이면 같은 날은 먼저 등록한 것이 앞이다.

    테스트 코드: PA-015
    """
    # given: 10/1 두 건(먼저·나중)과 10/3 한 건
    await _put(meeting_case, "10/1 먼저", 1)
    await _put(meeting_case, "10/3", 3)
    await _put(meeting_case, "10/1 나중", 1)
    # when: 미팅 날짜 오름차순으로 읽는다
    found = await meeting_case.contents(order=SortOrder.ASC)
    # then: 10/1 먼저, 10/1 나중, 10/3 순이다
    assert found == ["10/1 먼저", "10/1 나중", "10/3"]


@pytest.mark.parametrize("order", [SortOrder.ASC, SortOrder.DESC])
async def test_text_sorts_tie_by_date_descending_then_id_descending_regardless_of_order(
    meeting_case: MeetingCase, order: SortOrder
) -> None:
    """텍스트 열의 동률은 방향과 무관하게 날짜 내림차순 -> id 내림차순이다.

    테스트 코드: PA-016
    """
    # given: 회사가 같고 날짜만 다른 기록 셋(최신 날짜는 둘)
    await _put(meeting_case, "오래된", 1)
    await _put(meeting_case, "최신 먼저", 9)
    await _put(meeting_case, "최신 나중", 9)
    # when: 파트너 열을 asc 또는 desc로 읽는다
    found = await meeting_case.contents(sort=PartnerMeetingSort.PARTNER, order=order)
    # then: 방향과 무관하게 최신 나중, 최신 먼저, 오래된 순이다
    assert found == ["최신 나중", "최신 먼저", "오래된"]


async def test_the_partner_sort_orders_by_lowercased_company_in_both_directions(
    meeting_case: MeetingCase,
) -> None:
    """파트너 정렬은 소문자 회사명 기준으로 양방향이 맞다.

    테스트 코드: PA-016
    """
    # given: 대소문자가 섞인 회사 셋
    await _put(meeting_case, "beta", 1, company="Beta")
    await _put(meeting_case, "acme", 2, company="acme")
    await _put(meeting_case, "gamma", 3, company="GAMMA")
    # when: 파트너 열을 오름차순과 내림차순으로 읽는다
    ascending = await meeting_case.contents(sort=PartnerMeetingSort.PARTNER, order=SortOrder.ASC)
    descending = await meeting_case.contents(sort=PartnerMeetingSort.PARTNER, order=SortOrder.DESC)
    # then: 소문자 값 순서대로 양방향이다
    assert ascending == ["acme", "beta", "gamma"]
    assert descending == ["gamma", "beta", "acme"]


async def test_the_content_sort_orders_by_lowercased_content(meeting_case: MeetingCase) -> None:
    """내용 정렬은 소문자 내용 기준이다.

    테스트 코드: PA-016
    """
    # given: 대소문자가 섞인 내용 셋
    await _put(meeting_case, "Banana", 1)
    await _put(meeting_case, "apple", 2)
    await _put(meeting_case, "Cherry", 3)
    # when: 내용 열을 오름차순으로 읽는다
    found = await meeting_case.contents(sort=PartnerMeetingSort.CONTENT, order=SortOrder.ASC)
    # then: apple, Banana, Cherry 순이다
    assert found == ["apple", "Banana", "Cherry"]


async def test_the_author_sort_uses_the_display_name_or_the_login_id_including_resigned(
    meeting_case: MeetingCase,
) -> None:
    """작성자 정렬은 표시 이름(없으면 아이디) 기준이고 퇴사자도 포함한다.

    테스트 코드: PA-016, PA-017
    """
    # given: 표시 이름 Bravo, 이름 없이 아이디 alpha, 표시 이름 Charlie(퇴사)의 기록
    bravo = await meeting_case.author(uid("sort-a"), "Bravo", login_id="sort-a")
    alpha = await meeting_case.author(uid("sort-b"), None, login_id="alpha")
    charlie = await meeting_case.author(uid("sort-c"), "Charlie", login_id="sort-c")
    await _put(meeting_case, "by bravo", 1, author=bravo)
    await _put(meeting_case, "by alpha", 2, author=alpha)
    await _put(meeting_case, "by charlie", 3, author=charlie)
    await meeting_case.resign(charlie)
    # when: 작성자 열을 오름차순과 내림차순으로 읽는다
    ascending = await meeting_case.contents(sort=PartnerMeetingSort.AUTHOR, order=SortOrder.ASC)
    descending = await meeting_case.contents(sort=PartnerMeetingSort.AUTHOR, order=SortOrder.DESC)
    # then: alpha, Bravo, Charlie 순이며 퇴사자의 기록도 나온다
    assert ascending == ["by alpha", "by bravo", "by charlie"]
    assert descending == ["by charlie", "by bravo", "by alpha"]


async def test_paging_follows_the_sort_order(meeting_case: MeetingCase) -> None:
    """쪽 나누기는 정렬 순서를 따른다.

    테스트 코드: PA-018
    """
    # given: 날짜가 다른 다섯 건
    for day in range(1, 6):
        await _put(meeting_case, f"d{day}", day)
    # when: offset 2, limit 2로 읽는다
    page = await meeting_case.contents(offset=2, limit=2)
    # then: 최신순 세 번째와 네 번째다
    assert page == ["d3", "d2"]
