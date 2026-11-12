"""DeleteContact: 참조하는 Deal이 하나라도 있으면 삭제할 수 없고, 없으면 물리 삭제된다.

한 Deal이 같은 연락처를 고객과 파트너로 둘 다 참조해도 1건으로 센다. 파트너 링크는 비활성이어도
참조(FK)이므로 막는다(Q11). Deal을 지우면 링크도 함께 지워져 연락처를 다시 지울 수 있다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.contact.delete_contact import DeleteContact
from app.application.deal.delete_deal import DeleteDeal
from app.domain.common.errors import InvalidStateError
from app.domain.contact.errors import ContactInUseError, ContactNotFoundError
from app.domain.contact.values import ContactId
from tests.factories import later, make_deal
from tests.factories_contact import make_customer, make_partner, register_customer, register_partner
from tests.factories_deal import SALES, seed_deal
from tests.fakes.file_storage import FakeFileStorage
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


def _in_use_message(count: int) -> str:
    return f"연결된 Deal이 {count}건 있어 삭제할 수 없습니다."


class TestDeleteUnreferencedContact:
    async def test_deletes_the_contact_physically_and_commits(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """참조 Deal이 없는 고객 연락처는 물리 삭제되고 커밋된다.

        테스트 코드: CT-064
        """
        # given: 참조 Deal이 없는 고객 연락처
        registered = await register_customer(uow_factory, clock)

        # when: 삭제한다
        await DeleteContact(uow_factory).execute(registered.id)

        # then: 더 이상 조회되지 않는다
        with pytest.raises(ContactNotFoundError):
            await uow.contacts.get(registered.id)
        assert uow.commits == 2

    async def test_a_partner_contact_is_deleted_the_same_way(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """참조 Deal이 없는 파트너 연락처도 같은 방식으로 삭제된다.

        테스트 코드: CT-064
        """
        # given: 참조 Deal이 없는 파트너 연락처
        registered = await register_partner(uow_factory, clock)

        # when: 삭제한다
        await DeleteContact(uow_factory).execute(registered.id)

        # then: 더 이상 조회되지 않는다
        with pytest.raises(ContactNotFoundError):
            await uow.contacts.get(registered.id)

    async def test_missing_contact_raises_not_found(self, uow_factory: UnitOfWorkFactory) -> None:
        """없는 id를 지우면 찾을 수 없다는 오류다.

        테스트 코드: CT-065
        """
        # when·then: 없는 id를 삭제한다 → 연락처 없음 오류다
        with pytest.raises(ContactNotFoundError):
            await DeleteContact(uow_factory).execute(ContactId(new_id()))

    async def test_deleting_twice_raises_not_found(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """이미 지운 연락처를 다시 지우면 찾을 수 없다는 오류다.

        테스트 코드: CT-065
        """
        # given: 이미 삭제한 연락처
        registered = await register_customer(uow_factory, clock)
        await DeleteContact(uow_factory).execute(registered.id)

        # when·then: 같은 id를 다시 삭제한다 → 연락처 없음 오류다
        with pytest.raises(ContactNotFoundError):
            await DeleteContact(uow_factory).execute(registered.id)

    async def test_other_contacts_are_untouched(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """한 연락처를 지워도 다른 연락처는 남는다.

        테스트 코드: CT-064
        """
        # given: 연락처 두 건
        kept = await register_customer(uow_factory, clock, name="김철수", email=None)
        removed = await register_customer(uow_factory, clock, name="박영희", email=None)

        # when: 하나를 삭제한다
        await DeleteContact(uow_factory).execute(removed.id)

        # then: 다른 하나는 남는다
        assert (await uow.contacts.get(kept.id)).id == kept.id


@pytest.mark.usefixtures("default_users")
class TestDeleteContactReferencedByDeals:
    async def test_customer_with_a_deal_cannot_be_deleted(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
    ) -> None:
        """고객으로 참조되는 연락처는 건수 문구와 함께 삭제가 거절되고 남는다.

        테스트 코드: CT-066
        """
        # given: Deal 한 건이 고객으로 참조하는 연락처
        customer = make_customer()
        await seed_deal(uow, customer=customer)
        commits = uow.commits

        # when: 삭제한다
        with pytest.raises(ContactInUseError) as error:
            await DeleteContact(uow_factory).execute(customer.id)

        # then: "연결된 Deal이 1건" 문구로 거절되고 연락처와 커밋 수는 그대로다
        assert str(error.value) == _in_use_message(1)
        assert (await uow.contacts.get(customer.id)).id == customer.id
        assert uow.commits == commits

    async def test_partner_with_a_deal_cannot_be_deleted(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
    ) -> None:
        """파트너로 참조되는 연락처도 삭제가 거절되고 남는다.

        테스트 코드: CT-067
        """
        # given: Deal 한 건이 파트너로 참조하는 연락처
        partner = make_partner()
        await seed_deal(uow, partner=partner)

        # when: 삭제한다
        with pytest.raises(ContactInUseError) as error:
            await DeleteContact(uow_factory).execute(partner.id)

        # then: 거절되고 연락처는 남는다
        assert str(error.value) == _in_use_message(1)
        assert (await uow.contacts.get(partner.id)).id == partner.id

    async def test_the_error_is_an_invalid_state(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
    ) -> None:
        """참조 중 삭제 거절은 잘못된 상태 오류(409)의 하위 종류다.

        테스트 코드: CT-066
        """
        # given: 고객으로 참조되는 연락처
        customer = make_customer()
        await seed_deal(uow, customer=customer)

        # when·then: 삭제한다 → 잘못된 상태 오류다
        with pytest.raises(InvalidStateError):
            await DeleteContact(uow_factory).execute(customer.id)

    async def test_the_message_counts_every_referencing_deal(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
    ) -> None:
        """거절 문구의 건수는 참조하는 Deal 수 전체다.

        테스트 코드: CT-068
        """
        # given: Deal 세 건이 고객으로 참조하는 연락처
        customer = make_customer()
        for number in range(3):
            await seed_deal(uow, code=f"20261016-A00{number}", customer=customer)

        # when: 삭제한다
        with pytest.raises(ContactInUseError) as error:
            await DeleteContact(uow_factory).execute(customer.id)

        # then: 문구에 3건이 담긴다
        assert str(error.value) == _in_use_message(3)

    async def test_one_deal_using_the_contact_as_customer_and_partner_counts_once(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
    ) -> None:
        """한 Deal이 같은 연락처를 고객과 파트너로 함께 참조해도 1건으로 센다.

        테스트 코드: CT-068
        """
        # given: 같은 연락처를 고객과 파트너로 함께 참조하는 Deal 한 건
        contact = make_customer()
        await seed_deal(uow, customer=contact, partner=contact)

        # when: 삭제한다
        with pytest.raises(ContactInUseError) as error:
            await DeleteContact(uow_factory).execute(contact.id)

        # then: 1건으로 센 문구다
        assert str(error.value) == _in_use_message(1)

    async def test_a_partner_link_that_is_no_longer_active_still_blocks_deletion(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
    ) -> None:
        """교체돼 비활성인 파트너 링크의 연락처도 삭제가 거절된다.

        테스트 코드: CT-067
        """
        # given: 파트너가 새 연락처로 교체돼 옛 링크가 비활성인 Deal
        old_partner, new_partner = make_partner(), make_partner(company="다른파트너", name="최민수")
        customer = make_customer()
        for contact in (customer, old_partner, new_partner):
            await uow.contacts.add(contact)
        deal = make_deal(customer_id=customer.id, partner_id=old_partner.id)
        deal.replace_partner(new_partner.id, later(5))
        await uow.deals.add(deal)

        # when: 옛 파트너 연락처를 삭제한다
        with pytest.raises(ContactInUseError) as error:
            await DeleteContact(uow_factory).execute(old_partner.id)

        # then: 1건으로 거절된다
        assert str(error.value) == _in_use_message(1)

    async def test_contact_can_be_deleted_after_its_deal_is_deleted(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """참조하던 Deal을 지우면 연락처를 지울 수 있다.

        테스트 코드: CT-069
        """
        # given: 고객으로 참조하던 Deal을 지운 상태
        customer = make_customer()
        deal = await seed_deal(uow, customer=customer)
        await DeleteDeal(uow_factory, clock, FakeFileStorage()).execute(
            deal.id.value, deal.id.value, SALES
        )

        # when: 연락처를 삭제한다
        await DeleteContact(uow_factory).execute(customer.id)

        # then: 연락처가 사라진다
        with pytest.raises(ContactNotFoundError):
            await uow.contacts.get(customer.id)

    async def test_deals_of_other_contacts_do_not_block_deletion(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """다른 연락처를 참조하는 Deal은 삭제를 막지 않는다.

        테스트 코드: CT-070
        """
        # given: 참조 없는 연락처와, 다른 연락처를 참조하는 Deal
        free = await register_customer(uow_factory, clock, name="김철수", email=None)
        busy = make_customer(name="박영희", email=None)
        await seed_deal(uow, customer=busy)

        # when: 참조 없는 연락처를 삭제한다
        await DeleteContact(uow_factory).execute(free.id)

        # then: 삭제된다
        with pytest.raises(ContactNotFoundError):
            await uow.contacts.get(free.id)
