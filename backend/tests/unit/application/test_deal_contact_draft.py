"""Deal 화면의 연락처 선택(ContactDraft, AC-08·09·10, R-7): 선택·갱신·같은 사람 재사용·갱신 이력.

연락처를 고르면 입력값으로 그 연락처를 갱신해 쓰고, 정보가 실제로 바뀌면 그 연락처를 참조하는
다른 모든 Deal(비활성 파트너 링크 포함, Q11)의 History에 한 건씩 남고 updated_at이 갱신된다.
"""

from typing import TYPE_CHECKING

from app.application.deal.register_deal import RegisterDeal
from app.domain.contact.errors import ContactNotFoundError, DuplicateContactError
from app.domain.contact.values import ContactKind
from app.domain.deal.errors import DealCodeIssueError
from tests.factories import later, make_deal
from tests.factories_contact import make_customer, make_partner
from tests.factories_deal import SALES, draft_of, make_create_input, make_draft, seed_deal
from tests.fakes.deal_code_source import FakeDealCodeSuffixSource
from tests.support.expect import raises_with
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.domain.contact.entities import Contact
    from app.domain.deal.entities import Deal
    from tests.unit.application.deal_env import DealEnv

NOT_FOUND = "연락처를 찾을 수 없습니다."
DUPLICATE = "이미 등록된 연락처입니다."
BEFORE_INFO = "직급 팀장 · 이메일 kim@neoine.example · 전화 010-1234-5678"
AFTER_INFO = "직급 이사 · 이메일 kim@neoine.example · 전화 010-1234-5678"
CUSTOMER_TARGET = "고객 연락처 정보 (네오인 김철수)"


async def _customer_with_deal(env: DealEnv, code: str = "20261016-A001") -> tuple[Contact, Deal]:
    """고객 연락처와 그것을 고객으로 참조하는 Deal(준비용, 이력 없음)."""
    customer = make_customer()
    return customer, await seed_deal(env.uow, code=code, customer=customer)


class TestPickingAnExistingContact:
    async def test_the_picked_contact_is_used_as_the_customer(self, env: DealEnv) -> None:
        customer, _ = await _customer_with_deal(env)

        view = await env.new_deal(customer=draft_of(customer))

        assert view.item.deal.customer_id == customer.id
        assert view.customer.id == customer.id

    async def test_unchanged_values_neither_update_the_contact_nor_leave_history(
        self, env: DealEnv
    ) -> None:
        customer, other = await _customer_with_deal(env)
        env.clock.advance(60)

        await env.new_deal(customer=draft_of(customer))

        assert (await env.uow.contacts.get(customer.id)).updated_at == customer.updated_at
        assert await env.history_rows(other.id.value) == []
        assert (await env.uow.deals.get(other.id)).updated_at == other.updated_at

    async def test_changed_values_update_the_contact(self, env: DealEnv) -> None:
        customer, _ = await _customer_with_deal(env)
        env.clock.advance(60)

        await env.new_deal(customer=draft_of(customer, title="이사", phone="02-123-4567"))

        stored = await env.uow.contacts.get(customer.id)
        assert stored.details.title == "이사"
        assert stored.details.phone is not None
        assert stored.details.phone.value == "02-123-4567"
        assert stored.updated_at > customer.updated_at

    async def test_a_change_is_logged_once_on_every_other_deal_using_the_contact(
        self, env: DealEnv
    ) -> None:
        customer, first = await _customer_with_deal(env)
        second = await seed_deal(env.uow, code="20261016-B002", customer=customer)
        env.clock.advance(60)

        view = await env.new_deal(customer=draft_of(customer, title="이사"))

        expected = [("contact", CUSTOMER_TARGET, BEFORE_INFO, AFTER_INFO)]
        assert await env.history_rows(first.id.value) == expected
        assert await env.history_rows(second.id.value) == expected
        # 새로 등록되는 Deal은 그 시점에 아직 연락처를 참조하지 않으므로 등록 이력뿐이다
        assert await env.history_rows(view.item.deal.id.value) == [
            ("created", "Deal 등록", "", "Deal 등록")
        ]

    async def test_the_log_is_authored_by_the_requester_and_touches_the_other_deal(
        self, env: DealEnv
    ) -> None:
        customer, other = await _customer_with_deal(env)
        env.clock.advance(60)

        await env.new_deal(customer=draft_of(customer, title="이사"))

        (entry,) = await env.uow.deal_history.list(other.id)
        assert entry.changed_by == SALES.user_id
        assert entry.changed_at == env.clock.now()
        assert (await env.uow.deals.get(other.id)).updated_at == env.clock.now()

    async def test_an_inactive_partner_link_still_gets_the_log(self, env: DealEnv) -> None:
        old_partner = make_partner()
        new_partner = make_partner(company="다른파트너", name="최민수")
        customer = make_customer()
        for contact in (customer, old_partner, new_partner):
            await env.uow.contacts.add(contact)
        deal = make_deal(code="20261016-A001", customer_id=customer.id, partner_id=old_partner.id)
        deal.replace_partner(new_partner.id, later(5))  # 이전 파트너 링크는 비활성이 된다
        await env.uow.deals.add(deal)
        env.clock.advance(60)

        await env.new_deal(
            customer=make_draft(company="신규고객"),
            partner=draft_of(old_partner, phone="02-999-8888"),
        )

        rows = await env.history_rows(deal.id.value)
        assert [(r[0], r[1]) for r in rows] == [
            ("contact", "파트너 연락처 정보 (한빛파트너스 이영희)")
        ]

    async def test_a_contact_of_the_other_kind_is_not_found(self, env: DealEnv) -> None:
        partner = make_partner()
        await seed_deal(env.uow, partner=partner)

        with raises_with(ContactNotFoundError, NOT_FOUND):
            await env.new_deal(customer=draft_of(partner))

    async def test_an_unknown_contact_id_is_not_found_and_stores_nothing(
        self, env: DealEnv
    ) -> None:
        with raises_with(ContactNotFoundError, NOT_FOUND):
            await env.new_deal(customer=make_draft(contact_id=new_id()))

        assert env.uow.deals._items == {}

    async def test_turning_the_picked_contact_into_another_known_person_conflicts(
        self, env: DealEnv
    ) -> None:
        first = make_customer(name="김철수", email="kim@neoine.example")
        second = make_customer(name="박영희", email="park@neoine.example")
        await seed_deal(env.uow, code="20261016-A001", customer=first)
        await seed_deal(env.uow, code="20261016-A002", customer=second)

        with raises_with(DuplicateContactError, DUPLICATE):
            await env.new_deal(customer=draft_of(first, name="박영희", email="park@neoine.example"))

        assert (await env.uow.contacts.get(first.id)).details.name == "김철수"  # 갱신되지 않았다

    async def test_a_picked_partner_keeps_its_kind_and_becomes_the_active_link(
        self, env: DealEnv
    ) -> None:
        partner = make_partner()
        await seed_deal(env.uow, partner=partner)

        view = await env.new_deal(partner=draft_of(partner, title="대표"))

        stored = await env.uow.contacts.get(partner.id)
        assert stored.kind is ContactKind.PARTNER
        assert stored.details.title == "대표"
        assert view.item.deal.active_partner_id() == partner.id

    async def test_a_failed_registration_rolls_the_contact_change_back(self, env: DealEnv) -> None:
        customer, other = await _customer_with_deal(env)
        taken = await seed_deal(env.uow, code="20260101-A7K2")  # NOW의 서울 날짜는 20260101
        always_taken = FakeDealCodeSuffixSource("A7K2")

        with raises_with(DealCodeIssueError, "Deal code를 발급하지 못했습니다. 다시 시도하세요."):
            await RegisterDeal(env.uow_factory, env.clock, always_taken).execute(
                make_create_input(customer=draft_of(customer, title="이사")), SALES
            )

        assert (await env.uow.contacts.get(customer.id)).details.title == "팀장"
        assert await env.history_rows(other.id.value) == []
        assert taken.id in env.uow.deals._items


class TestReusingTheSamePerson:
    async def test_the_same_company_and_name_reuses_the_contact_and_keeps_blank_values(
        self, env: DealEnv
    ) -> None:
        existing = make_customer()
        await seed_deal(env.uow, customer=existing)

        view = await env.new_deal(customer=make_draft(title=None, email=None, phone=None))

        assert view.item.deal.customer_id == existing.id
        stored = await env.uow.contacts.get(existing.id)
        assert stored.details == existing.details  # 빈 입력이 기존 값을 지우지 않았다

    async def test_a_value_missing_on_the_contact_is_filled_by_the_input(
        self, env: DealEnv
    ) -> None:
        existing = make_customer(email=None, title=None, phone=None)
        await seed_deal(env.uow, customer=existing)

        await env.new_deal(
            customer=make_draft(title="팀장", email="kim@neoine.example", phone="010-1234-5678")
        )

        stored = await env.uow.contacts.get(existing.id)
        assert stored.details.title == "팀장"
        assert stored.details.email is not None
        assert stored.details.email.value == "kim@neoine.example"

    async def test_a_different_email_means_a_different_person_and_a_new_contact(
        self, env: DealEnv
    ) -> None:
        existing = make_customer(email="kim@neoine.example")
        await seed_deal(env.uow, customer=existing)

        view = await env.new_deal(customer=make_draft(email="other@neoine.example"))

        assert view.item.deal.customer_id != existing.id
        customers = [c for c in env.uow.contacts._items.values() if c.kind is ContactKind.CUSTOMER]
        assert len(customers) == 2

    async def test_a_partner_of_the_same_name_is_not_the_same_customer(self, env: DealEnv) -> None:
        partner = make_partner(company="네오인", name="김철수", email=None)
        await seed_deal(env.uow, partner=partner)

        view = await env.new_deal(customer=make_draft(email=None))

        assert view.item.deal.customer_id != partner.id
        assert view.customer.kind is ContactKind.CUSTOMER

    async def test_a_new_person_creates_a_contact_and_logs_nothing_elsewhere(
        self, env: DealEnv
    ) -> None:
        customer, other = await _customer_with_deal(env)

        await env.new_deal(customer=make_draft(company="다른회사", name="오세훈"))

        assert await env.history_rows(other.id.value) == []
        assert len(env.uow.contacts._items) == 2  # 기존 고객 + 새 고객
        assert customer.id in env.uow.contacts._items

    async def test_new_customer_and_partner_get_the_next_contact_ids(self, env: DealEnv) -> None:
        view = await env.new_deal(
            customer=make_draft(company="다른회사", name="오세훈"),
            partner=make_draft(company="한빛", name="이영희"),
        )

        (partner_id,) = view.partner_contacts
        assert {view.customer.id, partner_id} == {1, 2}  # 두 연락처가 같은 시퀀스에서 번호를 받는다
        assert sorted(env.uow.contacts._items) == [1, 2]
