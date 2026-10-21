"""UpdateContact: 입력 검증 → 행 잠금 → 같은 사람 판정(자기 제외) → 저장. kind는 바뀌지 않는다.

AC-19·20·21. 구 UpdateCustomer/UpdatePartner 테스트(값 교체·시계·잘못된 입력은 변경 없음·없는 id)를
옮기고 같은 사람 규칙을 더했다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.contact.update_contact import UpdateContact as RealUpdateContact
from app.domain.common.errors import InvalidValueError
from app.domain.contact.errors import ContactNotFoundError, DuplicateContactError
from app.domain.contact.values import ContactId, ContactKind
from tests.factories_contact import make_contact_input, register_customer, register_partner
from tests.support.ids import new_id
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.application.contact.inputs import ContactInput
    from app.application.contact.update_contact import UpdateContact as UpdateContactType
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.contact.entities import Contact
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


class UpdateContact:
    """이 모듈은 값 교체·검증을 본다. 변경자(이력 작성자)는 R3에서 필수 인자가 되었고, 여기서는
    고정 admin id를 넘긴다(이력 검증은 test_update_contact_history.py)."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._real: UpdateContactType = RealUpdateContact(uow_factory, clock)

    async def execute(self, contact_id: ContactId, data: ContactInput) -> Contact:
        return await self._real.execute(contact_id, data, uid("boss"))


def _update_input(**overrides: str | None) -> ContactInput:
    return make_contact_input(None, **overrides)  # 수정 입력은 kind가 없다


class TestUpdateContact:
    async def test_replaces_details_and_uses_the_clock(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        registered = await register_customer(uow_factory, clock)
        clock.advance(300)

        updated = await UpdateContact(uow_factory, clock).execute(
            registered.id, _update_input(company="새회사", email=None, title=None)
        )

        stored = await uow.contacts.get(registered.id)
        assert stored.details.company == "새회사"
        assert stored.details.email is None
        assert stored.details.title is None
        assert updated.updated_at == clock.now()
        assert stored.created_at == registered.created_at
        assert uow.commits == 2

    @pytest.mark.parametrize("kind", list(ContactKind))
    async def test_keeps_the_kind(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        kind: ContactKind,
    ) -> None:
        register = register_customer if kind is ContactKind.CUSTOMER else register_partner
        registered = await register(uow_factory, clock)

        await UpdateContact(uow_factory, clock).execute(
            registered.id, _update_input(company="새회사")
        )

        assert (await uow.contacts.get(registered.id)).kind is kind

    @pytest.mark.parametrize(
        "overrides",
        [
            {"company": "네오 인"},
            {"email": "not-an-email"},
            {"phone": "010 1234 5678"},
            {"name": ""},
        ],
        ids=["company-whitespace", "email-format", "phone-whitespace", "name-empty"],
    )
    async def test_invalid_input_leaves_the_contact_unchanged(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        overrides: dict[str, str],
    ) -> None:
        registered = await register_customer(uow_factory, clock)

        with pytest.raises(InvalidValueError):
            await UpdateContact(uow_factory, clock).execute(
                registered.id, _update_input(**overrides)
            )

        assert (await uow.contacts.get(registered.id)).details == registered.details
        assert uow.commits == 1

    async def test_missing_contact_raises_not_found(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        with pytest.raises(ContactNotFoundError):
            await UpdateContact(uow_factory, clock).execute(ContactId(new_id()), _update_input())


class TestSamePersonOnUpdate:
    async def test_becoming_another_existing_person_conflicts_and_changes_nothing(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, name="김철수", email=None)
        other = await register_customer(uow_factory, clock, name="박영희", email=None)

        with pytest.raises(DuplicateContactError) as error:
            await UpdateContact(uow_factory, clock).execute(
                other.id, _update_input(name="김철수", email=None)
            )

        assert str(error.value) == "이미 등록된 연락처입니다."
        assert (await uow.contacts.get(other.id)).details.name == "박영희"
        assert uow.commits == 2

    async def test_keeping_its_own_identity_is_not_a_conflict(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        registered = await register_customer(uow_factory, clock, email=None)

        await UpdateContact(uow_factory, clock).execute(
            registered.id, _update_input(email=None, title="이사")
        )

        assert (await uow.contacts.get(registered.id)).details.title == "이사"

    async def test_changing_only_the_case_of_its_own_name_is_not_a_conflict(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        registered = await register_customer(uow_factory, clock, company="Acme", email=None)

        await UpdateContact(uow_factory, clock).execute(
            registered.id, _update_input(company="ACME", email=None)
        )

        assert (await uow.contacts.get(registered.id)).details.company == "ACME"

    async def test_becoming_a_namesake_with_another_email_is_allowed(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, name="김철수", email="kim1@neoine.example")
        other = await register_customer(
            uow_factory, clock, name="박영희", email="park@neoine.example"
        )

        await UpdateContact(uow_factory, clock).execute(
            other.id, _update_input(name="김철수", email="kim2@neoine.example")
        )

        assert (await uow.contacts.get(other.id)).details.name == "김철수"

    async def test_adding_an_email_to_become_the_same_person_as_one_without_email_conflicts(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, name="김철수", email=None)
        other = await register_customer(
            uow_factory, clock, name="박영희", email="park@neoine.example"
        )

        with pytest.raises(DuplicateContactError):
            await UpdateContact(uow_factory, clock).execute(
                other.id, _update_input(name="김철수", email="kim@neoine.example")
            )

    async def test_the_same_person_of_the_other_kind_is_not_a_conflict(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, name="김철수", email=None)
        partner = await register_partner(uow_factory, clock, name="이영희", email=None)

        await UpdateContact(uow_factory, clock).execute(
            partner.id, _update_input(name="김철수", email=None)
        )

        assert (await uow.contacts.get(partner.id)).details.name == "김철수"
