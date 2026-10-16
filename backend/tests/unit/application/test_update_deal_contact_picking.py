"""UpdateDeal에서 ContactDraft로 연락처를 고르고 고치기(AC-08·10, R2 리뷰 이월 2).

PATCH로 자기 Deal의 고객이나 활성 파트너를 contact_id로 골라 값을 바꾸면, 자기 Deal을 포함해
그 연락처를 참조하는 모든 Deal의 History에 contact 이력이 한 건씩 남고 updated_at이 갱신된다.
"""

from typing import TYPE_CHECKING, Any

from app.domain.contact.errors import ContactNotFoundError, DuplicateContactError
from app.domain.contact.values import ContactKind
from tests.factories_contact import make_customer
from tests.factories_deal import SALES, draft_of, make_draft, make_patch, seed_deal
from tests.support.expect import raises_with

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
    view = await env.new_deal()
    env.clock.advance(60)

    updated = await env.update.execute(
        view.item.deal.id.value,
        make_patch(customer=draft_of(view.customer, title="이사")),
        SALES,
    )

    assert (await env.uow.contacts.get(view.customer.id)).details.title == "이사"
    assert await env.changes(updated) == [("contact", CUSTOMER_TARGET, BEFORE_INFO, AFTER_INFO)]
    assert updated.item.deal.updated_at == env.clock.now()
    assert updated.item.deal.customer_id == view.customer.id


async def test_editing_the_picked_customer_also_logs_on_every_other_deal_using_it(
    env: DealEnv,
) -> None:
    view = await env.new_deal()
    other = await seed_deal(env.uow, code="20261016-B002", customer=view.customer)
    env.clock.advance(60)

    await env.update.execute(
        view.item.deal.id.value,
        make_patch(customer=draft_of(view.customer, title="이사")),
        SALES,
    )

    assert await env.history_rows(other.id.value) == [
        ("contact", CUSTOMER_TARGET, BEFORE_INFO, AFTER_INFO)
    ]
    assert (await env.uow.deals.get(other.id)).updated_at == env.clock.now()


async def test_editing_the_active_partner_logs_the_contact_info_but_not_a_partner_change(
    env: DealEnv,
) -> None:
    view = await env.new_deal(partner=make_draft(**PARTNER))
    partner = view.partner_contacts[view.item.deal.active_partner_id()]  # type: ignore[index]
    env.clock.advance(60)

    updated = await env.update.execute(
        view.item.deal.id.value,
        make_patch(partner=draft_of(partner, title="부장")),
        SALES,
    )

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
    view = await env.new_deal()
    env.clock.advance(60)

    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(customer=draft_of(view.customer)), SALES
    )

    assert await env.changes(updated) == []
    assert updated.item.deal.updated_at == view.item.deal.updated_at


async def test_picking_another_existing_customer_logs_the_customer_change(env: DealEnv) -> None:
    view = await env.new_deal()
    other = make_customer(company="대한상사", name="오세훈", email=None)
    await env.uow.contacts.add(other)
    await env.uow.commit()

    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(customer=draft_of(other)), SALES
    )

    assert updated.item.deal.customer_id == other.id
    assert await env.changes(updated) == [
        ("contact", "고객 연락처", "네오인 김철수", "대한상사 오세훈")
    ]


async def test_picking_a_contact_of_the_other_kind_is_not_found_and_changes_nothing(
    env: DealEnv,
) -> None:
    view = await env.new_deal(partner=make_draft(**PARTNER))
    partner = view.partner_contacts[view.item.deal.active_partner_id()]  # type: ignore[index]
    assert partner.kind is ContactKind.PARTNER

    with raises_with(ContactNotFoundError, "연락처를 찾을 수 없습니다."):
        await env.update.execute(
            view.item.deal.id.value, make_patch(customer=draft_of(partner)), SALES
        )

    stored = await env.uow.deals.get(view.item.deal.id)
    assert stored.customer_id == view.customer.id
    assert await env.changes(view) == []


async def test_turning_the_picked_contact_into_another_known_person_conflicts_and_changes_nothing(
    env: DealEnv,
) -> None:
    view = await env.new_deal()
    rival = make_customer(company="네오인", name="박영희", email=None)
    await env.uow.contacts.add(rival)
    await env.uow.commit()

    with raises_with(DuplicateContactError, "이미 등록된 연락처입니다."):
        await env.update.execute(
            view.item.deal.id.value,
            make_patch(customer=draft_of(view.customer, name="박영희", email=None)),
            SALES,
        )

    assert (await env.uow.contacts.get(view.customer.id)).details.name == "김철수"
    assert await env.changes(view) == []
