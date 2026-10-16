"""Deal 유스케이스 입력·준비 도우미(P1 R2 모델). 기본은 유효한 더미 값이다.

이 모듈은 `app.application.deal.inputs`를 모듈 수준에서 가져온다. Deal 모델과 무관한 공용 모듈
(`tests/factories.py`, `tests/fakes/*`)은 이 모듈을 가져오지 않는다.
"""

import itertools
from datetime import date
from typing import TYPE_CHECKING, Any

from app.application.deal.inputs import Actor, ContactDraftInput, DealCreateInput, DealPatchInput
from app.domain.auth.principal import Role
from tests.factories import NOW, make_deal
from tests.factories_contact import make_customer
from tests.support.user_ids import OWNER_ID

if TYPE_CHECKING:
    from uuid import UUID

    from app.application.deal.dto import DealView
    from app.domain.deal.history import DealHistoryEntry

    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
    from app.domain.contact.entities import Contact
    from app.domain.deal.entities import Deal
    from tests.fakes.deal_code_source import FakeDealCodeSuffixSource

SALES = Actor(user_id=OWNER_ID, role=Role.SALES)  # 기본 요청자: 기본 Owner(재직 sales)
_COMPANIES = itertools.count(1)


def make_draft(contact_id: UUID | None = None, **overrides: Any) -> ContactDraftInput:  # noqa: ANN401
    """연락처 입력(ContactDraft). 기본은 새 고객이다(contact_id None). overrides: company, name,
    title, email, phone."""
    values: dict[str, Any] = {
        "company": "네오인",
        "name": "김철수",
        "title": "팀장",
        "email": "kim@neoine.example",
        "phone": "010-1234-5678",
        **overrides,
    }
    return ContactDraftInput(contact_id=contact_id, **values)


def draft_of(contact: Contact, **overrides: Any) -> ContactDraftInput:  # noqa: ANN401
    """저장된 연락처를 그대로 고르는 입력(값이 같아 갱신·이력이 없다). overrides로 값을 바꾼다."""
    details = contact.details
    values: dict[str, Any] = {
        "company": details.company,
        "name": details.name,
        "title": details.title,
        "email": details.email.value if details.email else None,
        "phone": details.phone.value if details.phone else None,
        **overrides,
    }
    return ContactDraftInput(contact_id=contact.id, **values)


def make_create_input(**overrides: Any) -> DealCreateInput:  # noqa: ANN401
    """등록 입력(원시 타입). overrides는 DealCreateInput 필드명이다."""
    values: dict[str, Any] = {
        "name": "ERP 구축",
        "owner_user_id": OWNER_ID,
        "vendor": "SAP",
        "solution": "S/4HANA",
        "users": None,
        "status_key": "prospecting",
        "forecast_key": "pipeline",
        "revenue_amount": 150_000_000,
        "revenue_date": date(2026, 6, 30),
        "customer": make_draft(),
        "partner": None,
        "quote_submitted": None,
        "quote_submitted_date": None,
        "poc_state": None,
        "poc_completed_date": None,
        "procurement": "",
        "bant": {},  # 빠진 구분은 선택 안 함(None)이다
        **overrides,
    }
    return DealCreateInput(**values)


def make_patch(**fields: Any) -> DealPatchInput:  # noqa: ANN401
    """수정 입력. 넘긴 필드만 '보낸 필드'(provided)다. None도 보낸 값이다(예: partner=None=제거)."""
    return DealPatchInput(provided=frozenset(fields), **fields)


def new_customer(**overrides: Any) -> Contact:  # noqa: ANN401
    """회사명이 호출마다 다른 고객 연락처(저장하지 않음)."""
    return make_customer(company=f"고객{next(_COMPANIES)}", **overrides)


async def register_deal(
    uow_factory: UnitOfWorkFactory,
    clock: Clock,
    suffix_source: FakeDealCodeSuffixSource,
    *,
    actor: Actor = SALES,
    **overrides: Any,  # noqa: ANN401
) -> DealView:
    """RegisterDeal로 등록한다. customer를 생략하면 새 고객 연락처가 만들어진다."""
    from app.application.deal.register_deal import RegisterDeal  # noqa: PLC0415

    return await RegisterDeal(uow_factory, clock, suffix_source).execute(
        make_create_input(**overrides), actor
    )


async def seed_deal(
    uow: UnitOfWork,
    *,
    code: str = "20261016-A001",
    customer: Contact | None = None,
    partner: Contact | None = None,
    commit: bool = True,
    **overrides: Any,  # noqa: ANN401
) -> Deal:
    """유스케이스를 거치지 않고 Deal을 저장소에 직접 넣는다(고객·파트너 연락처 포함).

    overrides는 `make_deal`과 같다(owner_user_id, status_key, bant, 금액 등).
    """
    customer = customer or new_customer()
    if customer.id not in uow.contacts._items:  # type: ignore[attr-defined]
        await uow.contacts.add(customer)
    if partner is not None and partner.id not in uow.contacts._items:  # type: ignore[attr-defined]
        await uow.contacts.add(partner)
    deal = make_deal(
        overrides.pop("now", NOW),
        code=code,
        customer_id=customer.id,
        partner_id=partner.id if partner else None,
        **overrides,
    )
    await uow.deals.add(deal)
    if commit:
        await uow.commit()
    return deal


async def history_rows(
    uow_factory: UnitOfWorkFactory, code: str
) -> list[tuple[str, str, str, str]]:
    """Deal 이력을 오래된 순서로 (category, target, before, after) 목록으로 돌려준다."""
    from app.domain.deal.code import DealCode  # noqa: PLC0415

    async with uow_factory() as uow:
        entries: list[DealHistoryEntry] = list(await uow.deal_history.list(DealCode(code)))
    return [
        (str(e.draft.category), e.draft.target, e.draft.before, e.draft.after)
        for e in reversed(entries)
    ]
