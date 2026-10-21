"""연락처(고객·파트너를 통합한 contacts) 테스트용 생성 도우미. 기본은 유효한 더미 값이다.

이 모듈은 `app.domain.contact`, `app.application.contact`를 모듈 수준에서 가져온다. 연락처와
무관한 공용 모듈(`tests/factories.py`, `tests/fakes/*`)은 이 모듈을 사용 시점에 가져와야 한다.
"""

from typing import TYPE_CHECKING, Any

from app.application.contact.inputs import ContactInput
from app.application.contact.register_contact import RegisterContact
from app.domain.common.contact import Email, PhoneNumber
from app.domain.contact.entities import Contact
from app.domain.contact.values import ContactDetails, ContactId, ContactKind
from tests.factories import NOW
from tests.support.ids import new_id

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory

CUSTOMER_DEFAULTS: dict[str, Any] = {
    "company": "네오인",
    "name": "김철수",
    "title": "팀장",
    "email": "kim@neoine.example",
    "phone": "010-1234-5678",
}
PARTNER_DEFAULTS: dict[str, Any] = {
    "company": "한빛파트너스",
    "name": "이영희",
    "title": "이사",
    "email": "lee@hanbit.example",
    "phone": "02-123-4567",
}


def _defaults(kind: ContactKind) -> dict[str, Any]:
    return CUSTOMER_DEFAULTS if kind is ContactKind.CUSTOMER else PARTNER_DEFAULTS


def only(field: str, value: object) -> dict[str, Any]:
    """필드 하나만 덮어쓰는 overrides(`**only("email", None)`). 값 타입을 Any로 연다."""
    return {field: value}


def make_contact_details(
    kind: ContactKind = ContactKind.CUSTOMER,
    **overrides: Any,  # noqa: ANN401
) -> ContactDetails:
    """overrides: company, name, title, email, phone (email·phone은 str 또는 값 객체/None)."""
    values = {**_defaults(kind), **overrides}
    email, phone = values["email"], values["phone"]
    return ContactDetails(
        company=values["company"],
        name=values["name"],
        title=values["title"],
        email=Email(email) if isinstance(email, str) else email,
        phone=PhoneNumber(phone) if isinstance(phone, str) else phone,
    )


def make_contact(
    kind: ContactKind = ContactKind.CUSTOMER,
    now: datetime = NOW,
    *,
    entity_id: ContactId | None = None,
    **overrides: Any,  # noqa: ANN401
) -> Contact:
    """저장하지 않은 연락처. overrides는 `make_contact_details`와 같다."""
    details = make_contact_details(kind, **overrides)
    return Contact.create(
        kind, details, now, entity_id=ContactId(new_id()) if entity_id is None else entity_id
    )


def make_customer(now: datetime = NOW, **overrides: Any) -> Contact:  # noqa: ANN401
    return make_contact(ContactKind.CUSTOMER, now, **overrides)


def make_partner(now: datetime = NOW, **overrides: Any) -> Contact:  # noqa: ANN401
    return make_contact(ContactKind.PARTNER, now, **overrides)


def make_contact_input(
    kind: ContactKind | None = ContactKind.CUSTOMER,
    **overrides: Any,  # noqa: ANN401
) -> ContactInput:
    """등록·수정 입력(원시 타입). 수정 입력은 kind=None. overrides: company, name 등 원시 문자열."""
    values = {**_defaults(kind or ContactKind.CUSTOMER), **overrides}
    return ContactInput(
        kind=kind,
        company=values["company"],
        name=values["name"],
        title=values["title"],
        email=values["email"],
        phone=values["phone"],
    )


async def register_customer(
    uow_factory: UnitOfWorkFactory,
    clock: Clock,
    **overrides: Any,  # noqa: ANN401
) -> Contact:
    """공개 유스케이스(RegisterContact)로 고객 연락처를 등록한다. Deal 테스트의 선행 데이터용."""
    return await RegisterContact(uow_factory, clock).execute(
        make_contact_input(ContactKind.CUSTOMER, **overrides)
    )


async def register_partner(
    uow_factory: UnitOfWorkFactory,
    clock: Clock,
    **overrides: Any,  # noqa: ANN401
) -> Contact:
    """공개 유스케이스(RegisterContact)로 파트너 연락처를 등록한다."""
    return await RegisterContact(uow_factory, clock).execute(
        make_contact_input(ContactKind.PARTNER, **overrides)
    )
