"""UpdateDeal에서 ContactDraft로 연락처를 고르고 고치기(R2 리뷰 이월 2).

PATCH로 자기 Deal의 고객이나 활성 파트너를 contact_id로 골라 값을 바꾸면, 자기 Deal을 포함해
그 연락처를 참조하는 모든 Deal의 History에 contact 이력이 한 건씩 남고 updated_at이 갱신된다.
"""

from typing import TYPE_CHECKING, Any

from app.domain.contact.errors import ContactNotFoundError, DuplicateContactError
from app.domain.contact.values import ContactKind
from tests.factories_contact import make_customer
from tests.factories_deal import SALES, draft_of, make_draft, make_patch, seed_deal
from tests.support.expect import raises_with
from tests.support.ids import new_id

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv

CUSTOMER_TARGET = "고객 연락처 정보 (네오인 김철수)"
BEFORE_INFO = "직급 팀장 · 이메일 kim@neoine.example · 전화 010-1234-5678"
AFTER_INFO = "직급 이사 · 이메일 kim@neoine.example · 전화 010-1234-5678"
PARTNER_TARGET = "파트너 연락처 정보 (코어테크 민지훈)"
PARTNER: dict[str, Any] = {
    "company": "코어테크",
    "name": "민지훈",
    "title": "이사",
    "email": "min@core.example",
    "phone": "02-123-4567",
}


async def test_editing_the_picked_customer_logs_on_the_own_deal_and_touches_it(
    env: DealEnv,
) -> None:
    """자기 Deal의 고객을 골라 값을 고치면 자기 Deal에 이력이 남고 수정 시각이 갱신된다.

    테스트 코드: DE-068
    """
    # given: 고객이 있는 Deal.
    view = await env.new_deal()
    env.clock.advance(60)

    # when: 고객 직급을 고쳐 수정한다.
    updated = await env.update.execute(
        view.item.deal.id.value,
        make_patch(customer=draft_of(view.customer, title="이사")),
        SALES,
    )

    # then: 연락처가 갱신되고 자기 Deal에 연락처 이력 1건, updated_at이 서버 시각이다.
    assert (await env.uow.contacts.get(view.customer.id)).details.title == "이사"
    assert await env.changes(updated) == [("contact", CUSTOMER_TARGET, BEFORE_INFO, AFTER_INFO)]
    assert updated.item.deal.updated_at == env.clock.now()
    assert updated.item.deal.customer_id == view.customer.id


async def test_editing_the_picked_customer_also_logs_on_every_other_deal_using_it(
    env: DealEnv,
) -> None:
    """같은 고객을 쓰는 다른 Deal에도 이력이 남고 수정 시각이 갱신된다.

    테스트 코드: DE-068
    """
    # given: 같은 고객을 쓰는 Deal 둘.
    view = await env.new_deal()
    other = await seed_deal(env.uow, code="20261016-B002", customer=view.customer)
    env.clock.advance(60)

    # when: 한 Deal에서 고객 직급을 고친다.
    await env.update.execute(
        view.item.deal.id.value,
        make_patch(customer=draft_of(view.customer, title="이사")),
        SALES,
    )

    # then: 다른 Deal에도 연락처 이력이 남고 updated_at이 서버 시각이다.
    assert await env.history_rows(other.id.value) == [
        ("contact", CUSTOMER_TARGET, BEFORE_INFO, AFTER_INFO)
    ]
    assert (await env.uow.deals.get(other.id)).updated_at == env.clock.now()


async def test_editing_the_active_partner_logs_the_contact_info_but_not_a_partner_change(
    env: DealEnv,
) -> None:
    """활성 파트너의 값만 고치면 연락처 정보 이력만 남고 링크는 그대로다.

    테스트 코드: DE-068
    """
    # given: 활성 파트너가 있는 Deal.
    view = await env.new_deal(partner=make_draft(**PARTNER))
    partner = view.partner_contacts[view.item.deal.active_partner_id()]  # type: ignore[index]
    env.clock.advance(60)

    # when: 파트너 직급을 고쳐 수정한다.
    updated = await env.update.execute(
        view.item.deal.id.value,
        make_patch(partner=draft_of(partner, title="부장")),
        SALES,
    )

    # then: 파트너 링크는 1건 그대로이고 '파트너 연락처 정보' 이력이 남는다.
    assert len(updated.item.deal.partner_links) == 1  # 같은 파트너라 링크는 그대로
    assert await env.changes(updated) == [
        (
            "contact",
            PARTNER_TARGET,
            "직급 이사 · 이메일 min@core.example · 전화 02-123-4567",
            "직급 부장 · 이메일 min@core.example · 전화 02-123-4567",
        )
    ]


async def test_picking_the_same_values_leaves_no_history_and_keeps_the_update_time(
    env: DealEnv,
) -> None:
    """고른 연락처를 값 그대로 보내면 이력·수정 시각 변화가 없다.

    테스트 코드: DE-069
    """
    # given: 고객이 있는 Deal.
    view = await env.new_deal()
    env.clock.advance(60)

    # when: 고객을 값 그대로 골라 수정한다.
    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(customer=draft_of(view.customer)), SALES
    )

    # then: 이력이 없고 updated_at이 그대로다.
    assert await env.changes(updated) == []
    assert updated.item.deal.updated_at == view.item.deal.updated_at


async def test_picking_another_existing_customer_logs_the_customer_change(env: DealEnv) -> None:
    """다른 기존 고객을 고르면 고객 변경 이력이 남는다.

    테스트 코드: DE-067
    """
    # given: 다른 고객 연락처가 있다.
    view = await env.new_deal()
    other = make_customer(company="대한상사", name="오세훈", email=None)
    await env.uow.contacts.add(other)
    await env.uow.commit()

    # when: 그 고객을 골라 수정한다.
    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(customer=draft_of(other)), SALES
    )

    # then: Deal의 고객이 바뀌고 '고객 연락처' 이력이 남는다.
    assert updated.item.deal.customer_id == other.id
    assert await env.changes(updated) == [
        ("contact", "고객 연락처", "네오인 김철수", "대한상사 오세훈")
    ]


async def test_picking_a_contact_of_the_other_kind_is_not_found_and_changes_nothing(
    env: DealEnv,
) -> None:
    """다른 종류(파트너) 연락처를 고객으로 고르면 404이고 아무것도 바뀌지 않는다.

    테스트 코드: DE-070
    """
    # given: 파트너가 있는 Deal.
    view = await env.new_deal(partner=make_draft(**PARTNER))
    partner = view.partner_contacts[view.item.deal.active_partner_id()]  # type: ignore[index]
    assert partner.kind is ContactKind.PARTNER

    with raises_with(ContactNotFoundError, "연락처를 찾을 수 없습니다."):
        await env.update.execute(
            view.item.deal.id.value, make_patch(customer=draft_of(partner)), SALES
        )

    # when: 그 파트너를 고객으로 골라 수정한다.
    stored = await env.uow.deals.get(view.item.deal.id)
    # then: '연락처를 찾을 수 없습니다.' 오류이고 고객·이력이 그대로다.
    assert stored.customer_id == view.customer.id
    assert await env.changes(view) == []


async def test_turning_the_picked_contact_into_another_known_person_conflicts_and_changes_nothing(
    env: DealEnv,
) -> None:
    """고른 연락처를 이미 있는 다른 사람으로 바꾸면 409이고 아무것도 바뀌지 않는다.

    테스트 코드: DE-070
    """
    # given: 같은 회사의 다른 고객 연락처.
    view = await env.new_deal()
    rival = make_customer(company="네오인", name="박영희", email=None)
    await env.uow.contacts.add(rival)
    await env.uow.commit()

    # when·then: 고른 고객을 그 사람 이름으로 고쳐 수정한다
    #   → '이미 등록된 연락처입니다.' 오류이고 연락처·이력이 그대로다.
    with raises_with(DuplicateContactError, "이미 등록된 연락처입니다."):
        await env.update.execute(
            view.item.deal.id.value,
            make_patch(customer=draft_of(view.customer, name="박영희", email=None)),
            SALES,
        )

    assert (await env.uow.contacts.get(view.customer.id)).details.name == "김철수"
    assert await env.changes(view) == []


async def test_picking_an_unknown_contact_is_not_found_and_changes_nothing(env: DealEnv) -> None:
    """없는 contact_id를 고르면 404이고 Deal은 그대로다.

    테스트 코드: DE-070
    """
    # given: 고객이 있는 Deal
    view = await env.new_deal()

    # when: 없는 contact_id로 고객을 고른다
    with raises_with(ContactNotFoundError, "연락처를 찾을 수 없습니다."):
        await env.update.execute(
            view.item.deal.id.value, make_patch(customer=make_draft(contact_id=new_id())), SALES
        )

    # then: 오류이고 고객과 이력이 그대로다
    assert (await env.uow.deals.get(view.item.deal.id)).customer_id == view.customer.id
    assert await env.changes(view) == []
