"""Deal 목록 행을 화면용 `DealView`로 만든다: Owner 참조와 연락처를 한꺼번에 모은다."""

from typing import TYPE_CHECKING

from app.application.deal.dto import DealView
from app.domain.contact.errors import ContactNotFoundError
from app.domain.user.errors import UserNotFoundError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.application.ports.deal_repository import DealListItem
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.contact.entities import Contact
    from app.domain.contact.values import ContactId
    from app.domain.user.value_objects import UserId, UserRef


def _contact_ids(item: DealListItem) -> list[ContactId]:
    deal = item.deal
    return [deal.customer_id, *(link.contact_id for link in deal.partner_links)]


def _require(contacts: Mapping[ContactId, Contact], contact_id: ContactId) -> Contact:
    contact = contacts.get(contact_id)
    if contact is None:
        raise ContactNotFoundError(contact_id)
    return contact


def _require_owner(owners: Mapping[UserId, UserRef], user_id: UserId) -> UserRef:
    owner = owners.get(user_id)
    if owner is None:
        raise UserNotFoundError(user_id)
    return owner


async def build_views(uow: UnitOfWork, items: Sequence[DealListItem]) -> list[DealView]:
    owner_ids = {item.deal.details.owner_user_id for item in items}
    owners = await uow.users.get_refs(owner_ids) if owner_ids else {}
    wanted = {contact_id for item in items for contact_id in _contact_ids(item)}
    contacts = await uow.contacts.get_many(wanted) if wanted else {}
    return [
        DealView(
            item=item,
            owner=_require_owner(owners, item.deal.details.owner_user_id),
            customer=_require(contacts, item.deal.customer_id),
            partner_contacts={
                link.contact_id: _require(contacts, link.contact_id)
                for link in item.deal.partner_links
            },
        )
        for item in items
    ]
