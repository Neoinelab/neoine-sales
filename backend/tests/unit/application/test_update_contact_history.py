"""UpdateContact의 Deal History(Q11): admin이 고치면 참조하는 모든 Deal에 이력이 남는다.

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
    """고객 연락처를 고치면 그 고객을 쓰는 모든 Deal에 이력이 한 건씩 남고 Deal 수정 시각이 바뀐다.

    테스트 코드: CT-058
    """
    # given: 같은 고객 연락처를 쓰는 Deal 두 건과 admin
    first = await env.new_deal()
    second = await env.new_deal(customer=draft_of(first.customer))
    admin = await _admin_id(env)
    env.clock.advance(60)

    # when: admin이 고객 연락처의 직급을 바꾼다
    await _update(env, first.customer.id, admin, title="이사")

    # then: 두 Deal 모두에 고객 연락처 정보 이력 한 건이 남고 Deal 수정 시각이 서버 시각이다
    expected = [("contact", "고객 연락처 정보 (네오인 김철수)", BEFORE, AFTER)]
    for view in (first, second):
        assert await env.changes(view) == expected
        assert (await env.uow.deals.get(view.item.deal.id)).updated_at == env.clock.now()


async def test_the_history_author_is_the_admin_who_changed_the_contact(env: DealEnv) -> None:
    """이력의 변경자는 연락처를 고친 admin이고 시각은 서버 시각이다.

    테스트 코드: CT-059
    """
    # given: Deal 한 건과 admin
    view = await env.new_deal()
    admin = await _admin_id(env)
    env.clock.advance(60)

    # when: admin이 연락처를 고친다
    await _update(env, view.customer.id, admin, title="이사")

    # then: 최신 이력의 변경자는 admin이고 시각은 서버 시각이다
    newest = (await env.history.execute(view.item.deal.id.value, None))[0]
    assert newest.by.id == admin
    assert newest.entry.changed_at == env.clock.now()


async def test_changing_a_partner_logs_with_the_partner_target_even_after_it_was_replaced(
    env: DealEnv,
) -> None:
    """파트너 연락처를 고치면 교체돼 비활성인 링크의 Deal에도 파트너 연락처 정보 이력이 남는다.

    테스트 코드: CT-060
    """
    # given: 파트너가 다른 파트너로 교체된 Deal
    view = await env.new_deal(partner=make_draft(company="코어테크", name="민지훈"))
    old = view.partner_contacts[view.item.deal.active_partner_id()]  # type: ignore[index]
    await env.update.execute(
        view.item.deal.id.value,
        make_patch(partner=make_draft(company="에이원시스템", name="표성호")),
        SALES,
    )
    admin = await _admin_id(env)
    env.clock.advance(60)

    # when: 교체된 옛 파트너 연락처의 직급을 바꾼다
    await _update(env, old.id, admin, company="코어테크", name="민지훈", title="부장")

    # then: "파트너 연락처 정보" 이력 한 건이 남는다
    rows = [r for r in await env.changes(view) if r[1].startswith("파트너 연락처 정보")]
    assert [r[1] for r in rows] == ["파트너 연락처 정보 (코어테크 민지훈)"]
    assert rows[0][3].startswith("직급 부장")


async def test_an_unchanged_contact_logs_nothing_and_touches_no_deal(env: DealEnv) -> None:
    """값이 그대로인 수정은 Deal 이력도 Deal 수정 시각도 바꾸지 않는다.

    테스트 코드: CT-061
    """
    # given: Deal 한 건과 그 고객 연락처의 현재 값
    view = await env.new_deal()
    admin = await _admin_id(env)
    env.clock.advance(60)
    current = view.customer.details

    # when: 현재 값 그대로 수정한다
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

    # then: 이력이 없고 Deal 수정 시각도 그대로다
    assert await env.changes(view) == []
    assert (await env.uow.deals.get(view.item.deal.id)).updated_at == view.item.deal.updated_at


async def test_a_contact_without_deals_changes_without_any_history(env: DealEnv) -> None:
    """참조 Deal이 없는 연락처는 이력 없이 수정된다.

    테스트 코드: CT-062
    """
    # given: 어느 Deal도 참조하지 않는 파트너 연락처와 다른 Deal 하나
    other = await env.new_deal()
    idle = make_partner(company="한가한회사", name="김한가")
    await env.uow.contacts.add(idle)
    await env.uow.commit()
    admin = await _admin_id(env)

    # when: 그 연락처의 직급을 바꾼다
    await _update(env, idle.id, admin, company="한가한회사", name="김한가", title="상무")

    # then: 직급이 바뀌고 다른 Deal에는 이력이 없다
    assert (await env.uow.contacts.get(idle.id)).details.title == "상무"
    assert await env.changes(other) == []


async def test_a_rejected_update_leaves_no_history(env: DealEnv) -> None:
    """거절된 수정은 이력을 남기지 않는다.

    테스트 코드: CT-063
    """
    # given: 다른 사람이 이미 쓰는 이름을 가진 연락처 두 건과 각자의 Deal
    view = await env.new_deal()
    rival = await env.new_deal(customer=make_draft(company="네오인", name="박영희", email=None))
    admin = await _admin_id(env)

    # when: 첫째 연락처를 둘째와 같은 사람으로 수정한다
    with raises_with(DuplicateContactError, "이미 등록된 연락처입니다."):
        await _update(env, view.customer.id, admin, company="네오인", name="박영희", email=None)

    # then: 409로 거절되고 두 Deal 모두 이력이 없다
    assert await env.changes(view) == []
    assert await env.changes(rival) == []
