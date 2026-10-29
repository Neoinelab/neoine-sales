"""PartnerMeetingRepository.deal_choices 계약(AC8, P2): Fake와 SQL 구현에 같은 기대값.

활성 파트너 링크(unlinked_at 없음)의 연락처 회사명이 company와 대소문자 무시로 같은 Deal 전부.
Forecast와 무관(Won·Lost 포함). 정렬은 lower(name) COLLATE "C" -> code 오름차순.
"""

from typing import TYPE_CHECKING

from tests.unit.repositories.partner_meeting_case import HANBIT

if TYPE_CHECKING:
    from tests.unit.repositories.partner_meeting_case import MeetingCase


async def test_active_links_through_any_contact_of_the_company_are_listed(
    meeting_case: MeetingCase,
) -> None:
    first = await meeting_case.partner(HANBIT, "이영희")
    second = await meeting_case.partner(HANBIT, "박민수")
    a = await meeting_case.deal(name="A", partner=first)
    b = await meeting_case.deal(name="B", partner=second)
    await meeting_case.deal(name="타사", company="다른파트너")
    await meeting_case.deal(name="파트너 없음", company=None)

    found = await meeting_case.repository.deal_choices(HANBIT)

    assert [c.code for c in found] == [a, b]


async def test_the_company_name_is_matched_case_insensitively(meeting_case: MeetingCase) -> None:
    code = await meeting_case.deal(company="HanbitPartners")

    found = await meeting_case.repository.deal_choices("hanbitPARTNERS")

    assert [c.code for c in found] == [code]


async def test_a_choice_carries_the_code_the_name_and_the_customer_company(
    meeting_case: MeetingCase,
) -> None:
    code = await meeting_case.deal(name="ERP 구축", customer_company="네오인")

    (choice,) = await meeting_case.repository.deal_choices(HANBIT)

    assert (choice.code, choice.name, choice.customer_company) == (code, "ERP 구축", "네오인")


async def test_won_and_lost_deals_are_included(meeting_case: MeetingCase) -> None:
    open_deal = await meeting_case.deal(name="진행")
    won = await meeting_case.deal(name="수주", forecast_key="won", status_key="contract_completed")
    lost = await meeting_case.deal(name="실주", forecast_key="lost")

    found = await meeting_case.repository.deal_choices(HANBIT)

    assert {c.code for c in found} == {open_deal, won, lost}


async def test_an_unlinked_partner_is_not_listed_but_a_relinked_one_is(
    meeting_case: MeetingCase,
) -> None:
    code = await meeting_case.deal(company=HANBIT)
    await meeting_case.unlink(code)
    assert list(await meeting_case.repository.deal_choices(HANBIT)) == []

    again = await meeting_case.partner(HANBIT, "복귀담당")
    await meeting_case.relink(code, again)

    found = await meeting_case.repository.deal_choices(HANBIT)
    assert [c.code for c in found] == [code]


async def test_a_deal_that_switched_to_another_company_leaves_the_old_company(
    meeting_case: MeetingCase,
) -> None:
    code = await meeting_case.deal(company=HANBIT)
    replacement = await meeting_case.partner("새파트너")
    await meeting_case.relink(code, replacement)

    assert list(await meeting_case.repository.deal_choices(HANBIT)) == []
    assert [c.code for c in await meeting_case.repository.deal_choices("새파트너")] == [code]


async def test_choices_are_ordered_by_lowercased_name_then_code(
    meeting_case: MeetingCase,
) -> None:
    b_first = await meeting_case.deal(name="b 프로젝트")
    a_only = await meeting_case.deal(name="A 프로젝트")
    b_second = await meeting_case.deal(name="B 프로젝트")

    found = await meeting_case.repository.deal_choices(HANBIT)

    assert [c.code for c in found] == [a_only, b_first, b_second]


async def test_an_unknown_company_has_no_choices(meeting_case: MeetingCase) -> None:
    await meeting_case.deal()

    assert list(await meeting_case.repository.deal_choices("없는회사")) == []


async def test_a_customer_company_with_the_same_name_is_not_a_partner_link(
    meeting_case: MeetingCase,
) -> None:
    await meeting_case.deal(company=None, customer_company=HANBIT)

    assert list(await meeting_case.repository.deal_choices(HANBIT)) == []


async def test_a_customer_contact_with_the_same_company_name_never_adds_a_deal(
    meeting_case: MeetingCase,
) -> None:
    mine = await meeting_case.deal(name="내 Deal", company=HANBIT, customer_company="네오인")
    await meeting_case.deal(
        name="고객사가 같은 이름", company="다른파트너", customer_company=HANBIT
    )

    found = await meeting_case.repository.deal_choices(HANBIT)

    assert [c.code for c in found] == [mine]
