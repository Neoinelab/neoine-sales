"""Deal 삭제 영향 응답(AC7): 이력·Action·첨부·계약 건수뿐이다. 파트너 미팅 건수는 없다."""

from app.domain.auth.principal import Role
from tests.factories import make_deal, make_deal_code
from tests.factories_contact import make_customer
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.partner_meeting_http import URL, clients, item, post_one, seed_partners

IMPACT_KEYS = {"history_count", "action_count", "attachment_count", "license_contract_count"}


async def _deal(use_cases: FakeUseCases) -> str:
    code = make_deal_code("W001")
    customer = make_customer()
    await use_cases.uow.contacts.add(customer)
    await use_cases.uow.deals.add(make_deal(code=code, customer_id=customer.id))
    return code.value


async def test_deletion_impact_response_has_four_counts() -> None:
    use_cases = FakeUseCases()
    code = await _deal(use_cases)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].get(f"/api/v1/deals/{code}/deletion-impact")

    assert response.status_code == 200, response.text
    assert set(response.json()) == IMPACT_KEYS


async def test_recorded_meetings_do_not_appear_in_the_deletion_impact() -> None:
    use_cases = FakeUseCases()
    code = await _deal(use_cases)
    await seed_partners(use_cases)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        await post_one(c["kim"])
        await c["kim"].post(URL, json={"items": [item(), item()]})
        response = await c["kim"].get(f"/api/v1/deals/{code}/deletion-impact")

    assert set(response.json()) == IMPACT_KEYS
