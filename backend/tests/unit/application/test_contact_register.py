"""RegisterContact: 입력 검증 → 같은 사람 판정 → 저장(AC-19·20). Fake UoW."""

from typing import TYPE_CHECKING, Any

import pytest

from app.application.contact.register_contact import RegisterContact
from app.application.ports.contact_repository import ContactQuery
from app.domain.common.contact import Email
from app.domain.common.errors import AlreadyExistsError, InvalidValueError
from app.domain.contact.errors import DuplicateContactError
from app.domain.contact.values import ContactKind
from tests.factories_contact import make_contact_input, register_customer

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

DUPLICATE_MESSAGE = "이미 등록된 연락처입니다."


async def _stored(uow: FakeUnitOfWork, kind: ContactKind | None = None) -> list[str]:
    """저장된 연락처의 '회사/담당자/이메일' 목록(등록 순서와 무관하게 정렬)."""
    found = await uow.contacts.search(ContactQuery(kind=kind, limit=200))
    return sorted(
        f"{c.details.company}/{c.details.name}/{c.details.email.value if c.details.email else ''}"
        for c in found
    )


class TestRegisterContact:
    async def test_persists_the_contact_and_commits_once(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        contact = await RegisterContact(uow_factory, clock).execute(make_contact_input())

        assert uow.commits == 1
        stored = await uow.contacts.get(contact.id)
        assert stored.kind is ContactKind.CUSTOMER
        assert stored.details.company == "네오인"
        assert contact.created_at == clock.now()

    async def test_partner_kind_is_kept(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        contact = await RegisterContact(uow_factory, clock).execute(
            make_contact_input(ContactKind.PARTNER)
        )

        assert (await uow.contacts.get(contact.id)).kind is ContactKind.PARTNER

    async def test_builds_normalized_value_objects(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        contact = await RegisterContact(uow_factory, clock).execute(
            make_contact_input(email="Kim@Neoine.Example", title="  팀장 ")
        )

        assert contact.details.email == Email("kim@neoine.example")
        assert contact.details.title == "팀장"

    @pytest.mark.parametrize(
        "overrides",
        [{"email": "not-an-email"}, {"company": "네오 인"}, {"phone": "abc"}, {"name": ""}],
        ids=["email-format", "company-whitespace", "phone-format", "name-empty"],
    )
    async def test_invalid_input_stores_nothing_and_does_not_commit(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        overrides: dict[str, Any],
    ) -> None:
        with pytest.raises(InvalidValueError):
            await RegisterContact(uow_factory, clock).execute(make_contact_input(**overrides))

        assert uow.commits == 0
        assert await _stored(uow) == []


class TestSamePersonOnRegister:
    async def test_the_same_company_and_name_without_email_conflicts(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, email=None)

        with pytest.raises(DuplicateContactError) as error:
            await register_customer(uow_factory, clock, email=None)

        assert str(error.value) == DUPLICATE_MESSAGE
        assert isinstance(error.value, AlreadyExistsError)
        assert len(await _stored(uow)) == 1
        assert uow.commits == 1

    async def test_the_same_email_conflicts_even_when_the_case_differs(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, email="kim@neoine.example")

        with pytest.raises(DuplicateContactError):
            await register_customer(uow_factory, clock, email="KIM@Neoine.Example")

    async def test_company_and_name_are_compared_ignoring_case(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, company="Acme", name="Kim", email=None)

        with pytest.raises(DuplicateContactError):
            await register_customer(uow_factory, clock, company="ACME", name="KIM", email=None)

    async def test_a_company_with_a_special_capital_letter_conflicts_on_the_second_registration(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, company="İstanbul", name="Kim", email=None)

        with pytest.raises(DuplicateContactError):
            await register_customer(uow_factory, clock, company="İstanbul", name="Kim", email=None)

        assert len(await _stored(uow)) == 1

    async def test_a_candidate_returned_by_same_identity_is_not_filtered_again_by_case(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # 저장소(PG lower)가 "İSTANBUL2"를 "istanbul2"와 같은 회사로 본 상황을
        # 후보 주입으로 재현한다 (Fake의 Python lower는 PG와 달라 후보를 못 찾는다).
        await register_customer(uow_factory, clock, company="İSTANBUL2", name="Lee", email=None)
        stored = list(await uow.contacts.search(ContactQuery(limit=200)))

        async def same_identity(kind: ContactKind, company: str, name: str) -> list[Any]:
            return stored

        monkeypatch.setattr(uow.contacts, "same_identity", same_identity)

        with pytest.raises(DuplicateContactError):
            await register_customer(uow_factory, clock, company="istanbul2", name="Lee", email=None)

        assert len(await _stored(uow)) == 1

    async def test_a_different_email_is_a_namesake_and_is_registered(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, email="kim1@neoine.example")

        await register_customer(uow_factory, clock, email="kim2@neoine.example")

        assert len(await _stored(uow)) == 2

    async def test_filling_in_the_email_of_an_existing_contact_without_one_conflicts(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, email=None)

        with pytest.raises(DuplicateContactError):
            await register_customer(uow_factory, clock, email="kim@neoine.example")

    async def test_no_email_input_conflicts_with_a_namesake_that_has_an_email(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, email="kim@neoine.example")

        with pytest.raises(DuplicateContactError):
            await register_customer(uow_factory, clock, email=None)

    async def test_the_same_person_in_the_other_kind_is_not_a_conflict(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        use_case = RegisterContact(uow_factory, clock)
        await use_case.execute(make_contact_input(ContactKind.CUSTOMER, email=None))

        await use_case.execute(make_contact_input(ContactKind.PARTNER, email=None))

        assert len(await _stored(uow, ContactKind.CUSTOMER)) == 1
        assert len(await _stored(uow, ContactKind.PARTNER)) == 1
