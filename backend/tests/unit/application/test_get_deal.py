"""GetDeal(AC-23): 상세 조회. 없는 code와 형식이 틀린 code는 모두 같은 404 문구다."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.contact.values import ContactKind
from app.domain.deal.errors import DealNotFoundError
from tests.factories import later
from tests.factories_deal import SALES, make_draft, make_patch
from tests.support.expect import raises_with
from tests.support.user_ids import OWNER_ID

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv

NOT_FOUND = "Deal을 찾을 수 없습니다."


async def test_the_view_has_the_deal_owner_customer_and_partner_contacts(env: DealEnv) -> None:
    created = await env.new_deal(
        customer=make_draft(company="한빛은행", name="정민수"),
        partner=make_draft(company="코어테크", name="민지훈"),
    )

    view = await env.get.execute(created.item.deal.id.value)

    assert view.item.deal.id == created.item.deal.id
    assert (view.owner.id, view.owner.role, view.owner.resigned) == (OWNER_ID, Role.SALES, False)
    assert (view.customer.details.company, view.customer.kind) == ("한빛은행", ContactKind.CUSTOMER)
    active = view.item.deal.active_partner_id()
    assert active is not None
    assert view.partner_contacts[active].details.company == "코어테크"
    assert view.item.next_action is None
    assert view.item.last_updated_at == view.item.deal.updated_at


async def test_the_partner_contacts_include_replaced_partners(env: DealEnv) -> None:
    created = await env.new_deal(partner=make_draft(company="코어테크", name="민지훈"))
    old = created.item.deal.active_partner_id()
    updated = await env.update.execute(
        created.item.deal.id.value,
        make_patch(partner=make_draft(company="에이원시스템", name="표성호")),
        SALES,
    )

    view = await env.get.execute(created.item.deal.id.value)

    assert old is not None
    assert set(view.partner_contacts) == {
        link.contact_id for link in updated.item.deal.partner_links
    }
    assert view.partner_contacts[old].details.company == "코어테크"
    assert view.item.deal.active_partner_id() != old


async def test_the_owner_of_a_resigned_user_is_still_resolved(env: DealEnv) -> None:
    created = await env.new_deal()
    async with env.uow_factory() as uow:
        owner = await uow.users.get(OWNER_ID)
        owner.resign(later(1))
        await uow.users.update(owner)
        await uow.commit()

    view = await env.get.execute(created.item.deal.id.value)

    assert view.owner.resigned is True
    assert view.owner.label.endswith("(퇴사)")


@pytest.mark.parametrize("code", ["20261016-ZZZZ", "bad", "", "20261016-a7k2", "20261016-A7K2/x"])
async def test_an_unknown_or_malformed_code_is_not_found(env: DealEnv, code: str) -> None:
    with raises_with(DealNotFoundError, NOT_FOUND):
        await env.get.execute(code)
