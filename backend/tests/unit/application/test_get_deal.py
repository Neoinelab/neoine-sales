"""GetDeal: 상세 조회. 없는 code와 형식이 틀린 code는 모두 같은 404 문구다."""

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
    """Deal 상세는 Deal과 Owner(재직 sales)·고객·활성 파트너 연락처를 돌려준다.

    테스트 코드: DD-001
    """
    # given: 고객 한빛은행·파트너 코어테크 연락처가 있는 Deal
    created = await env.new_deal(
        customer=make_draft(company="한빛은행", name="정민수"),
        partner=make_draft(company="코어테크", name="민지훈"),
    )

    # when: Deal 상세를 읽는다
    view = await env.get.execute(created.item.deal.id.value)

    # then: Deal id, Owner(id·sales·재직), 고객·파트너 연락처가 돌아오고 다음 Action은 없다
    assert view.item.deal.id == created.item.deal.id
    assert (view.owner.id, view.owner.role, view.owner.resigned) == (OWNER_ID, Role.SALES, False)
    assert (view.customer.details.company, view.customer.kind) == ("한빛은행", ContactKind.CUSTOMER)
    active = view.item.deal.active_partner_id()
    assert active is not None
    assert view.partner_contacts[active].details.company == "코어테크"
    assert view.item.next_action is None
    assert view.item.last_updated_on == view.item.deal.created_at.astimezone().date()


async def test_the_partner_contacts_include_replaced_partners(env: DealEnv) -> None:
    """파트너를 교체해도 상세의 파트너 연락처에는 이전 파트너가 남고 활성 파트너는 새 파트너다.

    테스트 코드: DD-004
    """
    # given: 파트너 코어테크로 등록한 뒤 에이원시스템으로 교체한 Deal
    created = await env.new_deal(partner=make_draft(company="코어테크", name="민지훈"))
    old = created.item.deal.active_partner_id()
    updated = await env.update.execute(
        created.item.deal.id.value,
        make_patch(partner=make_draft(company="에이원시스템", name="표성호")),
        SALES,
    )

    # when: Deal 상세를 읽는다
    view = await env.get.execute(created.item.deal.id.value)

    # then: 파트너 연락처는 모든 링크의 연락처이고 이전 파트너도 남으며 활성은 새 파트너다
    assert old is not None
    assert set(view.partner_contacts) == {
        link.contact_id for link in updated.item.deal.partner_links
    }
    assert view.partner_contacts[old].details.company == "코어테크"
    assert view.item.deal.active_partner_id() != old


async def test_the_owner_of_a_resigned_user_is_still_resolved(env: DealEnv) -> None:
    """Owner가 퇴사해도 상세의 Owner가 퇴사 표기로 돌아온다.

    테스트 코드: DD-003
    """
    # given: Owner가 퇴사 처리된 Deal
    created = await env.new_deal()
    async with env.uow_factory() as uow:
        owner = await uow.users.get(OWNER_ID)
        owner.resign(later(1))
        await uow.users.update(owner)
        await uow.commit()

    # when: Deal 상세를 읽는다
    view = await env.get.execute(created.item.deal.id.value)

    # then: Owner는 퇴사 true이고 표기가 '(퇴사)'로 끝난다
    assert view.owner.resigned is True
    assert view.owner.label.endswith("(퇴사)")


@pytest.mark.parametrize("code", ["20261016-ZZZZ", "bad", "", "20261016-a7k2", "20261016-A7K2/x"])
async def test_an_unknown_or_malformed_code_is_not_found(env: DealEnv, code: str) -> None:
    """없는 code와 형식이 틀린 code의 상세 조회는 같은 문구의 찾을 수 없음 오류다.

    테스트 코드: DD-005
    """
    # when·then: 없는 code, 형식이 틀린 code, 소문자 code로 상세를 읽는다
    #   → 모두 'Deal을 찾을 수 없습니다.' 오류다
    with raises_with(DealNotFoundError, NOT_FOUND):
        await env.get.execute(code)
