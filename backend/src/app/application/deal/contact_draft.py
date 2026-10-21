"""Deal 화면의 연락처 선택(ContactDraft): 입력 검증, 같은 사람 판정·병합 계획, 반영.

계획(`plan_contact`)은 저장소를 읽기만 하고, 반영(`commit_contact`)이 저장·갱신·이력을 만든다.
프런트 `mock/gateway/contactPlan.ts`와 같은 규칙이다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.deal.contact_change_log import log_contact_change
from app.application.ids import new_contact_id
from app.domain.common.errors import InvalidValueError
from app.domain.contact.draft import merge_same_person
from app.domain.contact.entities import Contact
from app.domain.contact.errors import ContactNotFoundError, DuplicateContactError
from app.domain.contact.identity import find_same_person
from app.domain.contact.values import ContactId, ContactKind

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.deal.inputs import ContactDraftInput
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.contact.values import ContactDetails
    from app.domain.deal.code import DealCode
    from app.domain.user.value_objects import UserId

CUSTOMER_COMPANY_REQUIRED = "고객 회사명을 입력하세요."
CUSTOMER_NAME_REQUIRED = "고객 담당자명을 입력하세요."
PARTNER_INCOMPLETE = "파트너를 입력하면 회사명과 담당자명이 모두 필요합니다."


@dataclass(frozen=True, slots=True)
class CheckedDrafts:
    """형식 검증을 마친 연락처 입력. 보내지 않았거나 없는 쪽은 None."""

    customer: ContactDetails | None
    partner: ContactDetails | None


@dataclass(frozen=True, slots=True)
class ContactPlan:
    """연락처 처리 계획: 새로 만들거나(contact=None), 기존 연락처를 이 값으로 바꾼다."""

    kind: ContactKind
    details: ContactDetails
    contact: Contact | None
    changed: bool


@dataclass(frozen=True, slots=True)
class CommittedContact:
    """반영 결과: 연락처 id와, 연락처 갱신 이력 때문에 수정 시각이 바뀐 Deal들."""

    contact_id: ContactId
    touched: frozenset[DealCode]


def check_drafts(
    customer: ContactDraftInput | None, partner: ContactDraftInput | None
) -> CheckedDrafts:
    """Deal 폼 규칙(필수 입력)을 먼저, 그다음 연락처 형식 규칙을 고객, 파트너 순으로 검사한다."""
    if customer is not None:
        if customer.company == "":
            raise InvalidValueError(CUSTOMER_COMPANY_REQUIRED)
        if customer.name == "":
            raise InvalidValueError(CUSTOMER_NAME_REQUIRED)
    if partner is not None and (partner.company == "" or partner.name == ""):
        raise InvalidValueError(PARTNER_INCOMPLETE)
    return CheckedDrafts(
        customer=_details(customer, ContactKind.CUSTOMER),
        partner=_details(partner, ContactKind.PARTNER),
    )


def _details(draft: ContactDraftInput | None, kind: ContactKind) -> ContactDetails | None:
    return None if draft is None else draft.to_contact_input(kind).to_details()


async def plan_contact(
    uow: UnitOfWork, kind: ContactKind, draft: ContactDraftInput, details: ContactDetails
) -> ContactPlan:
    """contact_id가 있으면 그 연락처를 입력값으로 바꾸는 계획, 없으면 같은 사람 재사용 또는 신규."""
    if draft.contact_id is not None:
        return await _plan_picked(uow, kind, ContactId(draft.contact_id), details)
    await uow.contacts.lock_identity(kind, details.company, details.name)
    same = await uow.contacts.same_identity(kind, details.company, details.name)
    found = find_same_person(same, kind, details)
    if found is None:
        return ContactPlan(kind=kind, details=details, contact=None, changed=True)
    merged = merge_same_person(found.details, details)
    changed = not merged.same_as(found.details)
    return ContactPlan(kind=kind, details=merged, contact=found, changed=changed)


async def _plan_picked(
    uow: UnitOfWork, kind: ContactKind, contact_id: ContactId, details: ContactDetails
) -> ContactPlan:
    contact = await uow.contacts.get(contact_id, for_update=True)
    if contact.kind is not kind:
        raise ContactNotFoundError(contact_id)
    await uow.contacts.lock_identity(kind, details.company, details.name)
    same = await uow.contacts.same_identity(kind, details.company, details.name)
    if find_same_person(same, kind, details, exclude_id=contact.id) is not None:
        raise DuplicateContactError
    changed = not details.same_as(contact.details)
    return ContactPlan(kind=kind, details=details, contact=contact, changed=changed)


@dataclass(frozen=True, slots=True)
class ResolvedContacts:
    """고객·파트너 입력을 처리한 결과. 입력을 보내지 않은 쪽은 None(건드리지 않음)이다."""

    customer_id: ContactId | None
    partner_id: ContactId | None
    touched: frozenset[DealCode]

    def require_customer(self) -> ContactId:
        if self.customer_id is None:
            raise InvalidValueError(CUSTOMER_COMPANY_REQUIRED)
        return self.customer_id


async def resolve_contacts(
    uow: UnitOfWork,
    drafts: tuple[ContactDraftInput | None, ContactDraftInput | None],
    checked: CheckedDrafts,
    changed_by: UserId,
    now: datetime,
) -> ResolvedContacts:
    """고객·파트너 입력을 먼저 모두 계획한 뒤(오류가 있으면 아무것도 쓰지 않는다) 반영한다."""
    customer_draft, partner_draft = drafts
    customer_plan = await _plan_optional(
        uow, ContactKind.CUSTOMER, customer_draft, checked.customer
    )
    partner_plan = await _plan_optional(uow, ContactKind.PARTNER, partner_draft, checked.partner)
    customer = await _commit_optional(uow, customer_plan, changed_by, now)
    partner = await _commit_optional(uow, partner_plan, changed_by, now)
    touched: frozenset[DealCode] = frozenset()
    for committed in (customer, partner):
        if committed is not None:
            touched |= committed.touched
    return ResolvedContacts(
        customer_id=customer.contact_id if customer else None,
        partner_id=partner.contact_id if partner else None,
        touched=touched,
    )


async def _plan_optional(
    uow: UnitOfWork,
    kind: ContactKind,
    draft: ContactDraftInput | None,
    details: ContactDetails | None,
) -> ContactPlan | None:
    if draft is None or details is None:
        return None
    return await plan_contact(uow, kind, draft, details)


async def _commit_optional(
    uow: UnitOfWork, plan: ContactPlan | None, changed_by: UserId, now: datetime
) -> CommittedContact | None:
    return None if plan is None else await commit_contact(uow, plan, changed_by, now)


async def commit_contact(
    uow: UnitOfWork, plan: ContactPlan, changed_by: UserId, now: datetime
) -> CommittedContact:
    """계획을 반영한다. 기존 연락처의 정보가 실제로 바뀌면 참조하는 모든 Deal에 이력을 남긴다."""
    contact = plan.contact
    if contact is None:
        created = Contact.create(
            plan.kind, plan.details, now, entity_id=await new_contact_id(uow.ids)
        )
        await uow.contacts.add(created)
        return CommittedContact(created.id, frozenset())
    if not plan.changed:
        return CommittedContact(contact.id, frozenset())
    before = contact.details
    contact.update(plan.details, now)
    await uow.contacts.update(contact)
    touched = await log_contact_change(uow, contact, before, changed_by, now)
    return CommittedContact(contact.id, touched)
