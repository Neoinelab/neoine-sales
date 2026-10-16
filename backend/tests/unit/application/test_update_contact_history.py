"""UpdateContact의 Deal History(AC-10, Q11): admin이 고치면 참조하는 모든 Deal에 이력이 남는다.

고객 참조와 비활성 포함 모든 파트너 링크의 Deal에 category=contact 한 건씩, 요청한 admin이
변경자이고 그 Deal들의 updated_at이 갱신된다. 정보가 그대로면 이력도 갱신도 없다.
`UpdateContact.execute(contact_id, data, changed_by)`가 변경자를 받는다.
"""

from typing import TYPE_CHECKING

from app.application.contact.update_contact import UpdateContact
from app.domain.auth.principal import Role
from app.domain.contact.errors import DuplicateContactError
from tests.factories_contact import make_contact_input, make_partner
from tests.factories_deal import SALES, draft_of, make_draft, make_patch
from tests.support.auth_seed import seed_user
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from app.domain.contact.values import ContactId
    from app.domain.user.value_objects import UserId
    from tests.unit.application.deal_env import DealEnv

BEFORE = "직급 팀장 · 이메일 kim@neoine.example · 전화 010-1234-5678"
AFTER = "직급 이사 · 이메일 kim@neoine.example · 전화 010-1234-5678"


async def _admin_id(env: DealEnv) -> UserId:
    return (await seed_user(env.uow_factory, "boss", Role.ADMIN)).id


async def _update(
    env: DealEnv, contact_id: ContactId, changed_by: UserId, **overrides: str | None
) -> None:
    """관리 화면의 연락처 수정(전체 교체). overrides 밖의 값은 팩토리 기본값(네오인 김철수)이다."""
    data = make_contact_input(None, **overrides)
    await UpdateContact(env.uow_factory, env.clock).execute(contact_id, data, changed_by)


async def test_changing_a_customer_logs_on_every_deal_that_uses_it(env: DealEnv) -> None:
    first = await env.new_deal()
    second = await env.new_deal(customer=draft_of(first.customer))
    admin = await _admin_id(env)
    env.clock.advance(60)

    await _update(env, first.customer.id, admin, title="이사")

    expected = [("contact", "고객 연락처 정보 (네오인 김철수)", BEFORE, AFTER)]
    for view in (first, second):
        assert await env.changes(view) == expected
        assert (await env.uow.deals.get(view.item.deal.id)).updated_at == env.clock.now()


async def test_the_history_author_is_the_admin_who_changed_the_contact(env: DealEnv) -> None:
    view = await env.new_deal()
    admin = await _admin_id(env)
    env.clock.advance(60)

    await _update(env, view.customer.id, admin, title="이사")

    newest = (await env.history.execute(view.item.deal.id.value, None))[0]
    assert newest.by.id == admin
    assert newest.entry.changed_at == env.clock.now()


async def test_changing_a_partner_logs_with_the_partner_target_even_after_it_was_replaced(
    env: DealEnv,
) -> None:
    view = await env.new_deal(partner=make_draft(company="코어테크", name="민지훈"))
    old = view.partner_contacts[view.item.deal.active_partner_id()]  # type: ignore[index]
    await env.update.execute(
        view.item.deal.id.value,
        make_patch(partner=make_draft(company="에이원시스템", name="표성호")),
        SALES,
    )
    admin = await _admin_id(env)
    env.clock.advance(60)

    await _update(env, old.id, admin, company="코어테크", name="민지훈", title="부장")

    rows = [r for r in await env.changes(view) if r[1].startswith("파트너 연락처 정보")]
    assert [r[1] for r in rows] == ["파트너 연락처 정보 (코어테크 민지훈)"]
    assert rows[0][3].startswith("직급 부장")


async def test_an_unchanged_contact_logs_nothing_and_touches_no_deal(env: DealEnv) -> None:
    view = await env.new_deal()
    admin = await _admin_id(env)
    env.clock.advance(60)
    current = view.customer.details

    await _update(
        env,
        view.customer.id,
        admin,
        company=current.company,
        name=current.name,
        title=current.title,
        email=current.email.value if current.email else None,
        phone=current.phone.value if current.phone else None,
    )

    assert await env.changes(view) == []
    assert (await env.uow.deals.get(view.item.deal.id)).updated_at == view.item.deal.updated_at


async def test_a_contact_without_deals_changes_without_any_history(env: DealEnv) -> None:
    other = await env.new_deal()
    idle = make_partner(company="한가한회사", name="김한가")
    await env.uow.contacts.add(idle)
    await env.uow.commit()
    admin = await _admin_id(env)

    await _update(env, idle.id, admin, company="한가한회사", name="김한가", title="상무")

    assert (await env.uow.contacts.get(idle.id)).details.title == "상무"
    assert await env.changes(other) == []


async def test_a_rejected_update_leaves_no_history(env: DealEnv) -> None:
    view = await env.new_deal()
    rival = await env.new_deal(customer=make_draft(company="네오인", name="박영희", email=None))
    admin = await _admin_id(env)

    with raises_with(DuplicateContactError, "이미 등록된 연락처입니다."):
        await _update(env, view.customer.id, admin, company="네오인", name="박영희", email=None)

    assert await env.changes(view) == []
    assert await env.changes(rival) == []
