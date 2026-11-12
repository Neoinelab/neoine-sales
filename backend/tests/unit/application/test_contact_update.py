"""UpdateContact: 입력 검증 → 행 잠금 → 같은 사람 판정(자기 제외) → 저장. kind는 바뀌지 않는다.

 ·21. 구 UpdateCustomer/UpdatePartner 테스트(값 교체·시계·잘못된 입력은 변경 없음·없는 id)를
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
        """수정하면 모든 값이 바뀌고 등록 시각은 그대로, 수정 시각은 서버 시각이다.

        테스트 코드: CT-046, CT-047
        """
        # given: 등록된 고객 연락처와 5분 뒤의 서버 시각
        registered = await register_customer(uow_factory, clock)
        clock.advance(300)

        # when: 회사명을 바꾸고 이메일·직급을 비워 수정한다
        updated = await UpdateContact(uow_factory, clock).execute(
            registered.id, _update_input(company="새회사", email=None, title=None)
        )

        # then: 값이 교체되고 비운 값은 없어지며 시각 규칙이 지켜진다
        stored = await uow.contacts.get(registered.id)
        assert stored.details.company == "새회사"
        assert stored.details.email is None
        assert stored.details.title is None
        assert updated.updated_at == clock.now()
        assert stored.created_at == registered.created_at
        assert uow.commits == 2

    async def test_unchanged_values_still_refresh_the_update_time(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """값이 하나도 바뀌지 않아도 수정 시각은 서버 시각으로 갱신된다.

        테스트 코드: CT-046
        """
        # given: 등록된 연락처와 5분 뒤의 서버 시각
        registered = await register_customer(uow_factory, clock)
        clock.advance(300)

        # when: 같은 값으로 수정한다
        await UpdateContact(uow_factory, clock).execute(registered.id, _update_input())

        # then: 값은 그대로이고 수정 시각만 서버 시각이 된다
        stored = await uow.contacts.get(registered.id)
        assert stored.details == registered.details
        assert stored.updated_at == clock.now()
        assert stored.created_at == registered.created_at

    async def test_omitted_optional_values_are_cleared_on_update(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """직급·이메일·전화를 null로 보내면 지워진다.

        테스트 코드: CT-047
        """
        # given: 직급·이메일·전화가 모두 있는 연락처
        registered = await register_customer(uow_factory, clock)

        # when: 선택 값을 모두 null로 수정한다
        await UpdateContact(uow_factory, clock).execute(
            registered.id, _update_input(title=None, email=None, phone=None)
        )

        # then: 세 값이 모두 없다
        details = (await uow.contacts.get(registered.id)).details
        assert (details.title, details.email, details.phone) == (None, None, None)

    @pytest.mark.parametrize("kind", list(ContactKind))
    async def test_keeps_the_kind(
        self,
        uow: FakeUnitOfWork,
        uow_factory: UnitOfWorkFactory,
        clock: FixedClock,
        kind: ContactKind,
    ) -> None:
        """수정해도 종류는 그대로다.

        테스트 코드: CT-046
        """
        # given: 해당 종류의 연락처
        register = register_customer if kind is ContactKind.CUSTOMER else register_partner
        registered = await register(uow_factory, clock)

        # when: 회사명을 바꿔 수정한다
        await UpdateContact(uow_factory, clock).execute(
            registered.id, _update_input(company="새회사")
        )

        # then: 종류가 그대로다
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
        """공백·형식이 틀린 값으로 수정하면 거절되고 기존 값이 남는다.

        테스트 코드: CT-050
        """
        # given: 등록된 연락처
        registered = await register_customer(uow_factory, clock)

        # when: 공백·이메일 형식·빈 담당자명 같은 잘못된 값으로 수정한다
        with pytest.raises(InvalidValueError):
            await UpdateContact(uow_factory, clock).execute(
                registered.id, _update_input(**overrides)
            )

        # then: 값이 그대로이고 추가 커밋이 없다
        assert (await uow.contacts.get(registered.id)).details == registered.details
        assert uow.commits == 1

    async def test_missing_contact_raises_not_found(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """없는 연락처를 수정하면 찾을 수 없다는 오류다.

        테스트 코드: CT-051
        """
        # when·then: 없는 id를 수정한다 → 연락처 없음 오류다
        with pytest.raises(ContactNotFoundError) as error:
            await UpdateContact(uow_factory, clock).execute(ContactId(new_id()), _update_input())
        assert str(error.value) == "연락처를 찾을 수 없습니다."


class TestSamePersonOnUpdate:
    async def test_becoming_another_existing_person_conflicts_and_changes_nothing(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """이미 있는 다른 사람과 같아지게 수정하면 409이고 그대로 남는다.

        테스트 코드: CT-052
        """
        # given: 서로 다른 두 연락처
        await register_customer(uow_factory, clock, name="김철수", email=None)
        other = await register_customer(uow_factory, clock, name="박영희", email=None)

        # when: 둘째를 첫째와 같은 담당자명으로 수정한다
        with pytest.raises(DuplicateContactError) as error:
            await UpdateContact(uow_factory, clock).execute(
                other.id, _update_input(name="김철수", email=None)
            )

        # then: 이미 등록된 연락처 오류이고 둘째는 그대로다
        assert str(error.value) == "이미 등록된 연락처입니다."
        assert (await uow.contacts.get(other.id)).details.name == "박영희"
        assert uow.commits == 2

    async def test_keeping_its_own_identity_is_not_a_conflict(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """자기 회사명·담당자명을 유지하고 다른 값만 바꾸는 것은 충돌이 아니다.

        테스트 코드: CT-053
        """
        # given: 이메일 없는 연락처
        registered = await register_customer(uow_factory, clock, email=None)

        # when: 회사명·담당자명은 두고 직급만 바꾼다
        await UpdateContact(uow_factory, clock).execute(
            registered.id, _update_input(email=None, title="이사")
        )

        # then: 수정된다

        assert (await uow.contacts.get(registered.id)).details.title == "이사"

    async def test_changing_only_the_case_of_its_own_name_is_not_a_conflict(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """자기 회사명의 대소문자만 바꾸는 수정은 충돌이 아니다.

        테스트 코드: CT-054
        """
        # given: "Acme" 연락처
        registered = await register_customer(uow_factory, clock, company="Acme", email=None)

        # when: 회사명을 "ACME"로 바꾼다
        await UpdateContact(uow_factory, clock).execute(
            registered.id, _update_input(company="ACME", email=None)
        )

        # then: 수정된다
        assert (await uow.contacts.get(registered.id)).details.company == "ACME"

    async def test_becoming_a_namesake_with_another_email_is_allowed(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """다른 이메일을 가진 동명이인이 되는 수정은 된다.

        테스트 코드: CT-055
        """
        # given: 이메일이 있는 김철수와 이메일이 있는 박영희
        await register_customer(uow_factory, clock, name="김철수", email="kim1@neoine.example")
        other = await register_customer(
            uow_factory, clock, name="박영희", email="park@neoine.example"
        )

        # when: 박영희를 다른 이메일의 김철수로 수정한다
        await UpdateContact(uow_factory, clock).execute(
            other.id, _update_input(name="김철수", email="kim2@neoine.example")
        )

        # then: 동명이인으로 수정된다
        assert (await uow.contacts.get(other.id)).details.name == "김철수"

    async def test_adding_an_email_to_become_the_same_person_as_one_without_email_conflicts(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """이메일을 채워 이메일 없는 다른 연락처와 같은 사람이 되면 409다.

        테스트 코드: CT-056
        """
        # given: 이메일 없는 김철수와 이메일 있는 박영희
        await register_customer(uow_factory, clock, name="김철수", email=None)
        other = await register_customer(
            uow_factory, clock, name="박영희", email="park@neoine.example"
        )

        # when·then: 박영희를 김철수 이름에 이메일을 채워 수정한다 → 같은 사람으로 거절된다
        with pytest.raises(DuplicateContactError):
            await UpdateContact(uow_factory, clock).execute(
                other.id, _update_input(name="김철수", email="kim@neoine.example")
            )

    async def test_the_same_person_of_the_other_kind_is_not_a_conflict(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """다른 종류의 같은 사람과 같아지는 수정은 충돌이 아니다.

        테스트 코드: CT-057
        """
        # given: 고객 김철수와 파트너 이영희
        await register_customer(uow_factory, clock, name="김철수", email=None)
        partner = await register_partner(uow_factory, clock, name="이영희", email=None)

        # when: 파트너를 고객과 같은 이름으로 수정한다
        await UpdateContact(uow_factory, clock).execute(
            partner.id, _update_input(name="김철수", email=None)
        )

        # then: 수정된다
        assert (await uow.contacts.get(partner.id)).details.name == "김철수"
