"""RegisterContact: 입력 검증 → 같은 사람 판정 → 저장. Fake UoW."""

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
        """고객 연락처를 등록하면 저장되고 등록·수정 시각은 서버 시각이다.

        테스트 코드: CT-001
        """
        # when: 고객 연락처를 등록한다
        contact = await RegisterContact(uow_factory, clock).execute(make_contact_input())

        # then: 한 번 커밋되어 저장되고 종류·회사명·시각이 맞다
        assert uow.commits == 1
        stored = await uow.contacts.get(contact.id)
        assert stored.kind is ContactKind.CUSTOMER
        assert stored.details.company == "네오인"
        assert contact.created_at == clock.now()
        assert contact.updated_at == contact.created_at

    async def test_partner_kind_is_kept(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """파트너 연락처를 등록하면 종류가 파트너로 저장된다.

        테스트 코드: CT-001
        """
        # when: 파트너 연락처를 등록한다
        contact = await RegisterContact(uow_factory, clock).execute(
            make_contact_input(ContactKind.PARTNER)
        )

        # then: 저장된 종류가 파트너다
        assert (await uow.contacts.get(contact.id)).kind is ContactKind.PARTNER

    async def test_builds_normalized_value_objects(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """이메일은 소문자로, 직급은 앞뒤 공백을 지워 저장한다.

        테스트 코드: CT-003, CT-004
        """
        # when: 대문자 이메일과 공백이 붙은 직급으로 등록한다
        contact = await RegisterContact(uow_factory, clock).execute(
            make_contact_input(email="Kim@Neoine.Example", title="  팀장 ")
        )

        # then: 정규화된 값이 저장된다
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
        """잘못된 입력은 거절되고 아무것도 저장하지 않으며 커밋하지 않는다.

        테스트 코드: CT-006, CT-008, CT-009, CT-010
        """
        # when: 이메일·전화 형식, 공백, 빈 담당자명 같은 잘못된 입력으로 등록한다
        with pytest.raises(InvalidValueError):
            await RegisterContact(uow_factory, clock).execute(make_contact_input(**overrides))

        # then: 저장된 연락처가 없고 커밋도 없다
        assert uow.commits == 0
        assert await _stored(uow) == []


class TestSamePersonOnRegister:
    async def test_the_same_company_and_name_without_email_conflicts(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """이메일 없이 같은 회사명·담당자명을 다시 등록하면 409이고 한 건만 남는다.

        테스트 코드: CT-017
        """
        # given: 이메일 없는 고객 연락처가 이미 있다
        await register_customer(uow_factory, clock, email=None)

        # when: 같은 회사명·담당자명을 이메일 없이 다시 등록한다
        with pytest.raises(DuplicateContactError) as error:
            await register_customer(uow_factory, clock, email=None)

        # then: 이미 등록된 연락처 오류이고 한 건만 남는다
        assert str(error.value) == DUPLICATE_MESSAGE
        assert isinstance(error.value, AlreadyExistsError)
        assert len(await _stored(uow)) == 1
        assert uow.commits == 1

    async def test_the_same_email_conflicts_even_when_the_case_differs(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """이메일까지 대소문자 무시로 같으면 같은 사람이라 409다.

        테스트 코드: CT-018
        """
        # given: 이메일이 있는 연락처가 있다
        await register_customer(uow_factory, clock, email="kim@neoine.example")

        # when·then: 대소문자만 다른 같은 이메일로 등록한다 → 같은 사람으로 거절된다
        with pytest.raises(DuplicateContactError):
            await register_customer(uow_factory, clock, email="KIM@Neoine.Example")

    async def test_company_and_name_are_compared_ignoring_case(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """회사명·담당자명은 대소문자만 달라도 같은 사람이다.

        테스트 코드: CT-019
        """
        # given: "Acme"/"Kim" 연락처가 있다
        await register_customer(uow_factory, clock, company="Acme", name="Kim", email=None)

        # when·then: "ACME"/"KIM"으로 등록한다 → 같은 사람으로 거절된다
        with pytest.raises(DuplicateContactError):
            await register_customer(uow_factory, clock, company="ACME", name="KIM", email=None)

    async def test_a_company_with_a_special_capital_letter_conflicts_on_the_second_registration(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """특수 대문자가 든 회사명도 같은 표기로 다시 등록하면 같은 사람이다.

        테스트 코드: CT-019
        """
        # given: 특수 대문자가 든 회사명의 연락처가 있다
        await register_customer(uow_factory, clock, company="İstanbul", name="Kim", email=None)

        # when: 같은 회사명·담당자명으로 다시 등록한다
        with pytest.raises(DuplicateContactError):
            await register_customer(uow_factory, clock, company="İstanbul", name="Kim", email=None)

        # then: 거절되고 한 건만 남는다
        assert len(await _stored(uow)) == 1

    async def test_a_candidate_returned_by_same_identity_is_not_filtered_again_by_case(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """저장소가 같은 회사로 본 후보는 대소문자로 다시 거르지 않고 같은 사람으로 판정한다.

        테스트 코드: CT-019
        """
        # given: 저장소(PG lower)가 "İSTANBUL2"를 "istanbul2"와 같은 회사로 본 상황을
        # 후보 주입으로 재현한다 (Fake의 Python lower는 PG와 달라 후보를 못 찾는다).
        await register_customer(uow_factory, clock, company="İSTANBUL2", name="Lee", email=None)
        stored = list(await uow.contacts.search(ContactQuery(limit=200)))

        async def same_identity(kind: ContactKind, company: str, name: str) -> list[Any]:
            return stored

        monkeypatch.setattr(uow.contacts, "same_identity", same_identity)

        # when: 후보와 대소문자가 다른 회사명으로 등록한다
        with pytest.raises(DuplicateContactError):
            await register_customer(uow_factory, clock, company="istanbul2", name="Lee", email=None)

        # then: 거절되고 한 건만 남는다
        assert len(await _stored(uow)) == 1

    async def test_a_different_email_is_a_namesake_and_is_registered(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """둘 다 이메일이 있고 서로 다르면 동명이인으로 등록된다.

        테스트 코드: CT-020
        """
        # given: 이메일이 있는 연락처가 있다
        await register_customer(uow_factory, clock, email="kim1@neoine.example")

        # when: 같은 회사명·담당자명에 다른 이메일로 등록한다
        await register_customer(uow_factory, clock, email="kim2@neoine.example")

        # then: 두 건이 저장된다
        assert len(await _stored(uow)) == 2

    async def test_filling_in_the_email_of_an_existing_contact_without_one_conflicts(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """이메일 없는 기존 연락처에 이메일을 채워 등록하면 같은 사람이라 409다.

        테스트 코드: CT-021
        """
        # given: 이메일 없는 연락처가 있다
        await register_customer(uow_factory, clock, email=None)

        # when·then: 같은 회사명·담당자명에 이메일을 채워 등록한다 → 같은 사람으로 거절된다
        with pytest.raises(DuplicateContactError):
            await register_customer(uow_factory, clock, email="kim@neoine.example")

    async def test_no_email_input_conflicts_with_a_namesake_that_has_an_email(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """이메일 없이 입력하면 이메일이 있는 기존 연락처와 같은 사람이라 409다.

        테스트 코드: CT-022
        """
        # given: 이메일이 있는 연락처가 있다
        await register_customer(uow_factory, clock, email="kim@neoine.example")

        # when·then: 같은 회사명·담당자명을 이메일 없이 등록한다 → 같은 사람으로 거절된다
        with pytest.raises(DuplicateContactError):
            await register_customer(uow_factory, clock, email=None)

    async def test_the_same_person_in_the_other_kind_is_not_a_conflict(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """종류가 다르면 같은 회사명·담당자명도 따로 등록된다.

        테스트 코드: CT-023
        """
        # given: 고객 연락처가 있다
        use_case = RegisterContact(uow_factory, clock)
        await use_case.execute(make_contact_input(ContactKind.CUSTOMER, email=None))

        # when: 같은 회사명·담당자명을 파트너로 등록한다
        await use_case.execute(make_contact_input(ContactKind.PARTNER, email=None))

        # then: 종류마다 한 건씩 있다
        assert len(await _stored(uow, ContactKind.CUSTOMER)) == 1
        assert len(await _stored(uow, ContactKind.PARTNER)) == 1
