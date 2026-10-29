"""ListPartnerDealChoices(AC8, P6): 회사의 활성 파트너 링크 Deal 선택지."""

from typing import TYPE_CHECKING

from tests.unit.application.partner_meeting_env import HANBIT

if TYPE_CHECKING:
    from tests.unit.application.partner_meeting_env import MeetingEnv


async def test_an_unknown_company_returns_an_empty_list(meeting_env: MeetingEnv) -> None:
    await meeting_env.deal()

    assert list(await meeting_env.choices.execute("없는회사")) == []


async def test_the_company_name_is_matched_case_insensitively(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal(company="HanbitPartners", name="ERP")

    found = await meeting_env.choices.execute("HANBITpartners")

    assert [c.code for c in found] == [code]


async def test_a_choice_carries_code_name_and_customer_company(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal(name="ERP 구축", customer_company="네오인")

    (choice,) = await meeting_env.choices.execute(HANBIT)

    assert (choice.code, choice.name, choice.customer_company) == (code, "ERP 구축", "네오인")


async def test_deals_through_any_contact_of_the_company_are_listed(
    meeting_env: MeetingEnv,
) -> None:
    first = await meeting_env.partner(HANBIT, "이영희")
    second = await meeting_env.partner(HANBIT, "박민수")
    a = await meeting_env.deal(name="A", partner=first)
    b = await meeting_env.deal(name="B", partner=second)

    found = await meeting_env.choices.execute(HANBIT)

    assert {c.code for c in found} == {a, b}


async def test_other_companies_and_deals_without_a_partner_are_not_listed(
    meeting_env: MeetingEnv,
) -> None:
    mine = await meeting_env.deal(name="내 것")
    await meeting_env.deal(name="타사", company="다른파트너")
    await meeting_env.deal(name="파트너 없음", company=None)

    found = await meeting_env.choices.execute(HANBIT)

    assert [c.code for c in found] == [mine]


async def test_won_and_lost_deals_are_listed(meeting_env: MeetingEnv) -> None:
    won = await meeting_env.deal(name="수주", forecast_key="won", status_key="contract_completed")
    lost = await meeting_env.deal(name="실주", forecast_key="lost")

    found = await meeting_env.choices.execute(HANBIT)

    assert {c.code for c in found} == {won, lost}


async def test_an_unlinked_partner_deal_is_not_listed(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal()
    await meeting_env.unlink_partner(code)

    assert list(await meeting_env.choices.execute(HANBIT)) == []


async def test_choices_are_ordered_by_name_then_code(meeting_env: MeetingEnv) -> None:
    second = await meeting_env.deal(name="b 프로젝트")
    first = await meeting_env.deal(name="A 프로젝트")
    third = await meeting_env.deal(name="b 프로젝트")

    found = await meeting_env.choices.execute(HANBIT)

    assert [c.code for c in found] == [first, second, third]
