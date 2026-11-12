"""Deal 화면의 연락처 선택(ContactDraft, R-7): 선택·갱신·같은 사람 재사용·갱신 이력.

연락처를 고르면 입력값으로 그 연락처를 갱신해 쓰고, 정보가 실제로 바뀌면 그 연락처를 참조하는
다른 모든 Deal(비활성 파트너 링크 포함, Q11)의 History에 한 건씩 남고 updated_at이 갱신된다.
"""

from typing import TYPE_CHECKING

from app.application.deal.register_deal import RegisterDeal
from app.domain.common.errors import InvalidValueError
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
        """고른 연락처가 그대로 고객으로 쓰인다.

        테스트 코드: DE-031
        """
        # given: 고객 연락처와 그것을 쓰는 Deal이 있다.
        customer, _ = await _customer_with_deal(env)

        # when: 그 연락처를 값 그대로 골라 새 Deal을 등록한다.
        view = await env.new_deal(customer=draft_of(customer))

        # then: 새 Deal의 고객이 그 연락처다.
        assert view.item.deal.customer_id == customer.id
        assert view.customer.id == customer.id

    async def test_unchanged_values_neither_update_the_contact_nor_leave_history(
        self, env: DealEnv
    ) -> None:
        """고른 연락처를 값 그대로 쓰면 연락처와 다른 Deal이 바뀌지 않는다.

        테스트 코드: DE-031
        """
        # given: 고객 연락처와 그것을 쓰는 다른 Deal이 있다.
        customer, other = await _customer_with_deal(env)
        env.clock.advance(60)

        # when: 값 그대로 골라 등록한다.
        await env.new_deal(customer=draft_of(customer))

        # then: 연락처 수정 시각, 다른 Deal의 이력·수정 시각이 그대로다.
        assert (await env.uow.contacts.get(customer.id)).updated_at == customer.updated_at
        assert await env.history_rows(other.id.value) == []
        assert (await env.uow.deals.get(other.id)).updated_at == other.updated_at

    async def test_changed_values_update_the_contact(self, env: DealEnv) -> None:
        """고른 연락처의 값을 고쳐 등록하면 연락처가 갱신된다.

        테스트 코드: DE-030
        """
        # given: 고객 연락처가 있다.
        customer, _ = await _customer_with_deal(env)
        env.clock.advance(60)

        # when: 직급·전화를 고쳐 등록한다.
        await env.new_deal(customer=draft_of(customer, title="이사", phone="02-123-4567"))

        # then: 연락처의 직급·전화가 바뀌고 수정 시각이 늘었다.
        stored = await env.uow.contacts.get(customer.id)
        assert stored.details.title == "이사"
        assert stored.details.phone is not None
        assert stored.details.phone.value == "02-123-4567"
        assert stored.updated_at > customer.updated_at

    async def test_a_change_is_logged_once_on_every_other_deal_using_the_contact(
        self, env: DealEnv
    ) -> None:
        """연락처가 바뀌면 그것을 쓰는 모든 Deal에 이력이 한 건씩 남고 새 Deal에는 없다.

        테스트 코드: DE-030
        """
        # given: 같은 고객을 쓰는 Deal 둘.
        customer, first = await _customer_with_deal(env)
        second = await seed_deal(env.uow, code="20261016-B002", customer=customer)
        env.clock.advance(60)

        # when: 직급을 고쳐 새 Deal을 등록한다.
        view = await env.new_deal(customer=draft_of(customer, title="이사"))

        # then: 기존 두 Deal에 연락처 이력 1건씩이고 새 Deal은 등록 이력뿐이다.
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
        """연락처 이력의 변경자는 요청자이고 그 Deal의 수정 시각이 갱신된다.

        테스트 코드: DE-030
        """
        # given: 고객을 쓰는 다른 Deal이 있다.
        customer, other = await _customer_with_deal(env)
        env.clock.advance(60)

        # when: 직급을 고쳐 등록한다.
        await env.new_deal(customer=draft_of(customer, title="이사"))

        # then: 이력 변경자·시각이 요청자·서버 시각이고 다른 Deal의 updated_at이 서버 시각이다.
        (entry,) = await env.uow.deal_history.list(other.id)
        assert entry.changed_by == SALES.user_id
        assert entry.changed_at == env.clock.now()
        assert (await env.uow.deals.get(other.id)).updated_at == env.clock.now()

    async def test_an_inactive_partner_link_still_gets_the_log(self, env: DealEnv) -> None:
        """비활성이 된 파트너 링크의 Deal에도 연락처 이력이 남는다.

        테스트 코드: DE-030
        """
        # given: 파트너가 교체되어 이전 파트너 링크가 비활성인 Deal.
        old_partner = make_partner()
        new_partner = make_partner(company="다른파트너", name="최민수")
        customer = make_customer()
        for contact in (customer, old_partner, new_partner):
            await env.uow.contacts.add(contact)
        deal = make_deal(code="20261016-A001", customer_id=customer.id, partner_id=old_partner.id)
        deal.replace_partner(new_partner.id, later(5))  # 이전 파트너 링크는 비활성이 된다
        await env.uow.deals.add(deal)
        env.clock.advance(60)

        # when: 이전 파트너를 골라 값을 고쳐 등록한다.
        await env.new_deal(
            customer=make_draft(company="신규고객"),
            partner=draft_of(old_partner, phone="02-999-8888"),
        )

        # then: 그 Deal에 파트너 연락처 정보 이력이 남는다.
        rows = await env.history_rows(deal.id.value)
        assert [(r[0], r[1]) for r in rows] == [
            ("contact", "파트너 연락처 정보 (한빛파트너스 이영희)")
        ]

    async def test_a_contact_of_the_other_kind_is_not_found(self, env: DealEnv) -> None:
        """다른 종류(파트너)의 연락처를 고객으로 고르면 404다.

        테스트 코드: DE-032
        """
        # given: 파트너 연락처가 있다.
        partner = make_partner()
        await seed_deal(env.uow, partner=partner)

        # when·then: 그 파트너를 고객으로 골라 등록한다 → '연락처를 찾을 수 없습니다.' 오류다.
        with raises_with(ContactNotFoundError, NOT_FOUND):
            await env.new_deal(customer=draft_of(partner))

    async def test_an_unknown_contact_id_is_not_found_and_stores_nothing(
        self, env: DealEnv
    ) -> None:
        """없는 연락처 id를 고르면 404이고 Deal이 만들어지지 않는다.

        테스트 코드: DE-032
        """
        # when: 없는 contact_id로 등록한다.
        with raises_with(ContactNotFoundError, NOT_FOUND):
            await env.new_deal(customer=make_draft(contact_id=new_id()))

        # then: '연락처를 찾을 수 없습니다.' 오류이고 Deal이 없다.
        assert env.uow.deals._items == {}

    async def test_turning_the_picked_contact_into_another_known_person_conflicts(
        self, env: DealEnv
    ) -> None:
        """고른 연락처를 이미 있는 다른 사람으로 바꾸면 409이고 갱신되지 않는다.

        테스트 코드: DE-033
        """
        # given: 서로 다른 두 고객 연락처.
        first = make_customer(name="김철수", email="kim@neoine.example")
        second = make_customer(name="박영희", email="park@neoine.example")
        await seed_deal(env.uow, code="20261016-A001", customer=first)
        await seed_deal(env.uow, code="20261016-A002", customer=second)

        # when: 첫 연락처를 둘째 사람의 이름·이메일로 고쳐 등록한다.
        with raises_with(DuplicateContactError, DUPLICATE):
            await env.new_deal(customer=draft_of(first, name="박영희", email="park@neoine.example"))

        # then: '이미 등록된 연락처입니다.' 오류이고 첫 연락처 이름은 그대로다.
        assert (await env.uow.contacts.get(first.id)).details.name == "김철수"  # 갱신되지 않았다

    async def test_a_picked_partner_keeps_its_kind_and_becomes_the_active_link(
        self, env: DealEnv
    ) -> None:
        """고른 파트너 연락처는 종류를 유지한 채 활성 링크가 된다.

        테스트 코드: DE-030
        """
        # given: 파트너 연락처가 있다.
        partner = make_partner()
        await seed_deal(env.uow, partner=partner)

        # when: 그 파트너의 직급을 고쳐 파트너로 등록한다.
        view = await env.new_deal(partner=draft_of(partner, title="대표"))

        # then: 연락처 종류는 파트너, 직급이 갱신, 활성 파트너가 그 연락처다.
        stored = await env.uow.contacts.get(partner.id)
        assert stored.kind is ContactKind.PARTNER
        assert stored.details.title == "대표"
        assert view.item.deal.active_partner_id() == partner.id

    async def test_a_failed_registration_rolls_the_contact_change_back(self, env: DealEnv) -> None:
        """code 발급 실패로 등록이 실패해도 고른 연락처 변경은 되돌려진다.

        테스트 코드: DE-034
        """
        # given: 고객 연락처, 그것을 쓰는 Deal, 항상 겹치는 code 소스.
        customer, other = await _customer_with_deal(env)
        taken = await seed_deal(env.uow, code="20260101-A7K2")  # NOW의 서울 날짜는 20260101
        always_taken = FakeDealCodeSuffixSource("A7K2")

        # when: 직급을 고쳐 등록한다.
        with raises_with(DealCodeIssueError, "Deal code를 발급하지 못했습니다. 다시 시도하세요."):
            await RegisterDeal(env.uow_factory, env.clock, always_taken).execute(
                make_create_input(customer=draft_of(customer, title="이사")), SALES
            )

        # then: 발급 실패 오류이고 연락처 직급·다른 Deal 이력이 그대로다.
        assert (await env.uow.contacts.get(customer.id)).details.title == "팀장"
        assert await env.history_rows(other.id.value) == []
        assert taken.id in env.uow.deals._items


class TestReusingTheSamePerson:
    async def test_the_same_company_and_name_reuses_the_contact_and_keeps_blank_values(
        self, env: DealEnv
    ) -> None:
        """같은 회사·이름이면 기존 연락처를 쓰고 빈 입력은 기존 값을 지우지 않는다.

        테스트 코드: DE-026
        """
        # given: 직급·이메일·전화가 있는 고객 연락처.
        existing = make_customer()
        await seed_deal(env.uow, customer=existing)

        # when: 같은 회사·이름에 빈 직급·이메일·전화로 등록한다.
        view = await env.new_deal(customer=make_draft(title=None, email=None, phone=None))

        # then: 기존 연락처를 쓰고 값은 그대로다.
        assert view.item.deal.customer_id == existing.id
        stored = await env.uow.contacts.get(existing.id)
        assert stored.details == existing.details  # 빈 입력이 기존 값을 지우지 않았다

    async def test_a_value_missing_on_the_contact_is_filled_by_the_input(
        self, env: DealEnv
    ) -> None:
        """기존 연락처에 없던 값은 입력으로 채워진다.

        테스트 코드: DE-027
        """
        # given: 직급·이메일·전화가 없는 고객 연락처.
        existing = make_customer(email=None, title=None, phone=None)
        await seed_deal(env.uow, customer=existing)

        # when: 같은 회사·이름에 값을 채워 등록한다.
        await env.new_deal(
            customer=make_draft(title="팀장", email="kim@neoine.example", phone="010-1234-5678")
        )

        # then: 연락처의 직급·이메일이 입력 값이 된다.
        stored = await env.uow.contacts.get(existing.id)
        assert stored.details.title == "팀장"
        assert stored.details.email is not None
        assert stored.details.email.value == "kim@neoine.example"

    async def test_a_different_email_means_a_different_person_and_a_new_contact(
        self, env: DealEnv
    ) -> None:
        """이메일이 다르면 다른 사람이라 새 연락처가 만들어진다.

        테스트 코드: DE-028
        """
        # given: kim@neoine.example 고객 연락처.
        existing = make_customer(email="kim@neoine.example")
        await seed_deal(env.uow, customer=existing)

        # when: 같은 회사·이름에 다른 이메일로 등록한다.
        view = await env.new_deal(customer=make_draft(email="other@neoine.example"))

        # then: 새 고객 연락처가 만들어져 고객 연락처가 2건이다.
        assert view.item.deal.customer_id != existing.id
        customers = [c for c in env.uow.contacts._items.values() if c.kind is ContactKind.CUSTOMER]
        assert len(customers) == 2

    async def test_a_partner_of_the_same_name_is_not_the_same_customer(self, env: DealEnv) -> None:
        """같은 회사·이름의 파트너는 같은 고객이 아니다.

        테스트 코드: DE-029
        """
        # given: 같은 회사·이름의 파트너 연락처.
        partner = make_partner(company="네오인", name="김철수", email=None)
        await seed_deal(env.uow, partner=partner)

        # when: 같은 값을 고객으로 입력해 등록한다.
        view = await env.new_deal(customer=make_draft(email=None))

        # then: 고객은 파트너와 다른 새 고객 연락처다.
        assert view.item.deal.customer_id != partner.id
        assert view.customer.kind is ContactKind.CUSTOMER

    async def test_a_new_person_creates_a_contact_and_logs_nothing_elsewhere(
        self, env: DealEnv
    ) -> None:
        """새 사람이면 새 연락처를 만들고 다른 Deal에는 이력이 남지 않는다.

        테스트 코드: DE-025
        """
        # given: 기존 고객과 그 Deal.
        customer, other = await _customer_with_deal(env)

        # when: 다른 회사·이름의 고객으로 등록한다.
        await env.new_deal(customer=make_draft(company="다른회사", name="오세훈"))

        # then: 연락처가 2건이 되고 기존 Deal 이력은 없다.
        assert await env.history_rows(other.id.value) == []
        assert len(env.uow.contacts._items) == 2  # 기존 고객 + 새 고객
        assert customer.id in env.uow.contacts._items

    async def test_new_customer_and_partner_get_the_next_contact_ids(self, env: DealEnv) -> None:
        """새 고객·파트너 연락처는 같은 시퀀스에서 번호를 받는다."""
        # when: 새 고객·새 파트너로 등록한다.
        view = await env.new_deal(
            customer=make_draft(company="다른회사", name="오세훈"),
            partner=make_draft(company="한빛", name="이영희"),
        )

        # then: 두 연락처 id가 1, 2다.
        (partner_id,) = view.partner_contacts
        assert {view.customer.id, partner_id} == {1, 2}  # 두 연락처가 같은 시퀀스에서 번호를 받는다
        assert sorted(env.uow.contacts._items) == [1, 2]


class TestFilledAndRolledBack:
    async def test_values_filled_into_a_reused_contact_are_logged_on_the_other_deals(
        self, env: DealEnv
    ) -> None:
        """같은 사람의 연락처에 없던 값을 채우면 그 연락처를 쓰는 다른 Deal에 이력이 남는다.

        테스트 코드: DE-027
        """
        # given: 직급·이메일·전화가 없는 고객 연락처와 그것을 쓰는 Deal
        existing = make_customer(email=None, title=None, phone=None)
        other = await seed_deal(env.uow, code="20261016-A001", customer=existing)
        env.clock.advance(60)

        # when: 같은 회사·이름에 직급·전화를 채워 새 Deal을 등록한다
        view = await env.new_deal(
            customer=make_draft(email=None, title="팀장", phone="02-123-4567")
        )

        # then: 연락처를 재사용해 값이 채워지고 다른 Deal에 연락처 이력이 1건 남는다
        stored = await env.uow.contacts.get(existing.id)
        assert view.item.deal.customer_id == existing.id
        assert (stored.details.title, stored.details.phone is not None) == ("팀장", True)
        rows = await env.history_rows(other.id.value)
        assert [(row[0], row[1]) for row in rows] == [
            ("contact", "고객 연락처 정보 (네오인 김철수)")
        ]
        assert (await env.uow.deals.get(other.id)).updated_at == env.clock.now()

    async def test_a_value_error_leaves_the_picked_contact_unchanged(self, env: DealEnv) -> None:
        """값 오류로 등록이 실패하면 고른 연락처도, 그것을 쓰는 다른 Deal도 바뀌지 않는다.

        테스트 코드: DE-034
        """
        # given: 고객 연락처와 그것을 쓰는 다른 Deal
        customer, other = await _customer_with_deal(env)
        env.clock.advance(60)

        # when: 고른 연락처의 직급을 고치되 금액을 0으로 하여 등록한다
        with raises_with(InvalidValueError, "매출금액은 1원 이상의 정수로 입력하세요."):
            await env.new_deal(customer=draft_of(customer, title="이사"), revenue_amount=0)

        # then: 금액 오류이고 연락처 값·다른 Deal 이력·수정 시각이 그대로다
        stored = await env.uow.contacts.get(customer.id)
        assert stored.details.title == "팀장"
        assert stored.updated_at == customer.updated_at
        assert await env.history_rows(other.id.value) == []
        assert (await env.uow.deals.get(other.id)).updated_at == other.updated_at
