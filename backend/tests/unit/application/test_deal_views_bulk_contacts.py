"""목록·상세·이력 이름 조회가 연락처를 id마다 읽지 않는다(N+1 해소).

Fake 연락처 저장소의 읽기 왕복 수(`round_trips`: get, get_many 각 1회)로 결과를 확인한다. 값은
묶어서 읽어도 그대로여야 하므로 응답 내용도 함께 본다.
"""

from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from tests.factories_deal import SALES, make_draft, make_patch

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


async def _five_deals(env: DealEnv) -> None:
    for number in range(5):
        await env.new_deal(
            customer=make_draft(company=f"고객사{number}", name=f"담당{number}", email=None),
            partner=make_draft(company=f"파트너사{number}", name=f"파트{number}", email=None),
        )


async def test_the_list_reads_all_contacts_of_the_page_in_one_round_trip(env: DealEnv) -> None:
    """목록은 한 페이지의 연락처를 한 번의 왕복으로 읽는다."""
    # given: Deal 5건과 초기화한 읽기 왕복 수
    await _five_deals(env)
    env.uow.contacts.round_trips = 0

    # when: 목록을 조회한다
    page = await env.list.execute(DealQuery())

    # then: 왕복은 1회 이하이고 내용은 그대로다
    assert env.uow.contacts.round_trips <= 1
    companies = {view.customer.details.company for view in page.items}
    assert companies == {f"고객사{n}" for n in range(5)}
    for view in page.items:
        active = view.item.deal.active_partner_id()
        assert active is not None
        assert view.partner_contacts[active].details.company.startswith("파트너사")


async def test_an_empty_page_does_not_read_contacts(env: DealEnv) -> None:
    """빈 페이지는 연락처를 읽지 않는다."""
    # given: Deal이 없고 읽기 왕복 수를 초기화한 상태
    env.uow.contacts.round_trips = 0

    # when: 목록을 조회한다
    page = await env.list.execute(DealQuery())

    # then: 항목이 없고 연락처 읽기도 없다
    assert page.items == []
    assert env.uow.contacts.round_trips == 0


async def test_the_detail_reads_its_contacts_in_one_round_trip(env: DealEnv) -> None:
    """상세는 연락처를 한 번의 왕복으로 읽는다."""
    # given: Deal 하나와 초기화한 읽기 왕복 수
    view = await env.new_deal(
        customer=make_draft(company="한빛은행", name="정민수"),
        partner=make_draft(company="코어테크", name="민지훈"),
    )
    env.uow.contacts.round_trips = 0

    # when: 상세를 조회한다
    detail = await env.get.execute(view.item.deal.id.value)

    # then: 왕복은 1회 이하이고 연락처 내용이 맞다
    assert env.uow.contacts.round_trips <= 1
    assert detail.customer.details.company == "한빛은행"
    assert len(detail.partner_contacts) == 1


async def test_a_plain_edit_reads_contacts_in_bulk_for_the_history_names_and_the_response(
    env: DealEnv,
) -> None:
    """단순 수정은 이력 이름 조회와 응답 조립에서 연락처를 묶어서 읽는다."""
    # given: Deal 하나와 초기화한 읽기 왕복 수
    view = await env.new_deal(
        customer=make_draft(company="한빛은행", name="정민수"),
        partner=make_draft(company="코어테크", name="민지훈"),
    )
    env.uow.contacts.round_trips = 0

    # when: 이름만 수정한다
    updated = await env.update.execute(view.item.deal.id.value, make_patch(name="B"), SALES)

    # then: 왕복은 2회 이하이고 응답 연락처가 맞다
    assert env.uow.contacts.round_trips <= 2  # 이름 조회 한 번 + 응답 조립 한 번
    assert updated.customer.details.company == "한빛은행"
