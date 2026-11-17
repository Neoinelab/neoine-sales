"""Deal 삭제 영향 응답: 이력·Action·첨부·계약·Comment 건수뿐이다. 파트너 미팅 건수는 없다."""

from app.domain.auth.principal import Role
from tests.factories import make_deal, make_deal_code
from tests.factories_contact import make_customer
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.partner_meeting_http import URL, clients, item, post_one, seed_partners

IMPACT_KEYS = {
    "history_count",
    "action_count",
    "attachment_count",
    "license_contract_count",
    "comment_count",
}


async def _deal(use_cases: FakeUseCases) -> str:
    code = make_deal_code("W001")
    customer = make_customer()
    await use_cases.uow.contacts.add(customer)
    await use_cases.uow.deals.add(make_deal(code=code, customer_id=customer.id))
    return code.value


async def test_deletion_impact_response_has_five_counts() -> None:
    """Deal 삭제 영향은 다섯 건수 키뿐이다(Comment 건수 포함, 미팅 건수는 없다).

    테스트 코드: PA-044
    """
    # given: Deal 하나와 sales 로그인
    use_cases = FakeUseCases()
    code = await _deal(use_cases)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        # when: 삭제 영향을 읽는다
        response = await c["kim"].get(f"/api/v1/deals/{code}/deletion-impact")
    # then: 200이고 키는 다섯 건수뿐이다
    assert response.status_code == 200, response.text
    assert set(response.json()) == IMPACT_KEYS


async def test_recorded_meetings_do_not_appear_in_the_deletion_impact() -> None:
    """미팅을 기록해도 Deal 삭제 영향에 미팅 건수가 생기지 않는다.

    테스트 코드: PA-044
    """
    # given: Deal 하나와 미팅 기록 셋
    use_cases = FakeUseCases()
    code = await _deal(use_cases)
    await seed_partners(use_cases)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        await post_one(c["kim"])
        await c["kim"].post(URL, json={"items": [item(), item()]})
        # when: 삭제 영향을 읽는다
        response = await c["kim"].get(f"/api/v1/deals/{code}/deletion-impact")
    # then: 키는 네 건수뿐이다
    assert set(response.json()) == IMPACT_KEYS
