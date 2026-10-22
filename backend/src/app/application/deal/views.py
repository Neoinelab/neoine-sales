"""Deal 목록 행을 화면용 `DealView`로 만든다: Owner 참조와 연락처를 한꺼번에 모은다.

Risk와 Status 체류 일수는 요청 시각 `now`의 업무 날짜(OS 로컬 시간대)로 계산하며,
미업데이트 기준 일수는 경고 기준 설정을 목록당 한 번만 읽는다(없으면 기본값).
"""

from typing import TYPE_CHECKING

from app.application.deal.dto import DealView, NamedRef
from app.domain.alert.thresholds import AlertThresholds
from app.domain.common.business_date import business_date
from app.domain.contact.errors import ContactNotFoundError
from app.domain.deal.risk import compute_risk, status_days
from app.domain.user.errors import UserNotFoundError
from app.domain.vendor.errors import VendorNotFoundError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime

    from app.application.ports.deal_repository import DealListItem
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.contact.entities import Contact
    from app.domain.contact.values import ContactId
    from app.domain.user.value_objects import UserId, UserRef
    from app.domain.vendor.entities import Vendor
    from app.domain.vendor.values import VendorId


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


def _vendor_ref(item: DealListItem, vendors: Mapping[VendorId, Vendor]) -> NamedRef | None:
    """Deal의 Vendor 참조. 참조가 사라진 경우는 FK가 막으므로 정상 경로에서는 없다."""
    vendor_id = item.deal.details.vendor_id
    if vendor_id is None:
        return None
    vendor = vendors.get(vendor_id)
    if vendor is None:
        raise VendorNotFoundError(vendor_id)
    return NamedRef(vendor.id, vendor.name)


async def load_thresholds(uow: UnitOfWork) -> AlertThresholds:
    """저장된 경고 기준, 없으면 기본값."""
    stored = await uow.alert_settings.get()
    return stored.thresholds if stored else AlertThresholds.default()


async def build_views(
    uow: UnitOfWork,
    items: Sequence[DealListItem],
    *,
    now: datetime,
    thresholds: AlertThresholds | None = None,
) -> list[DealView]:
    """경고 기준을 한 번 읽고(없으면 기본값) 각 행의 risk·status_days를 계산한다.

    thresholds를 넘기면 다시 읽지 않는다(목록 필터와 같은 기준을 쓰기 위해).
    """
    thresholds = thresholds or await load_thresholds(uow)
    today = business_date(now)
    owner_ids = {item.deal.details.owner_user_id for item in items}
    owners = await uow.users.get_refs(owner_ids) if owner_ids else {}
    wanted = {contact_id for item in items for contact_id in _contact_ids(item)}
    contacts = await uow.contacts.get_many(wanted) if wanted else {}
    vendors = (
        {v.id: v for v in await uow.vendors.list()}
        if any(item.deal.details.vendor_id is not None for item in items)
        else {}
    )
    return [
        DealView(
            item=item,
            owner=_require_owner(owners, item.deal.details.owner_user_id),
            customer=_require(contacts, item.deal.customer_id),
            partner_contacts={
                link.contact_id: _require(contacts, link.contact_id)
                for link in item.deal.partner_links
            },
            risk=compute_risk(
                forecast_key=item.deal.sync.forecast_key,
                due_date=item.next_action.due_date if item.next_action else None,
                last_updated_at=item.last_updated_at,
                today=today,
                stale_days=thresholds.stale_days,
            ),
            status_days=status_days(item.deal.status_changed_at, today),
            vendor=_vendor_ref(item, vendors),
        )
        for item in items
    ]
