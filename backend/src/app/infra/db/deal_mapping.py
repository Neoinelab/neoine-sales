"""Deal 엔티티와 ORM 행 사이의 변환. 판단 없이 값을 옮기기만 한다."""

from typing import TYPE_CHECKING

from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.contact.values import ContactId
from app.domain.deal.code import DealCode
from app.domain.deal.entities import Deal, PartnerLink
from app.domain.deal.sync import SyncState
from app.domain.deal.values import (
    BantSelection,
    DealDetails,
    Poc,
    PocState,
    Quote,
    QuoteSubmitted,
    RevenueAmount,
)
from app.domain.user.value_objects import UserId
from app.infra.db.models_deal import DealBantLabelRow, DealPartnerRow, DealRow

if TYPE_CHECKING:
    from collections.abc import Iterable


def apply_fields(row: DealRow, deal: Deal) -> None:
    """Deal의 폼 값과 수정 시각을 행에 쓴다(code·생성 시각은 바꾸지 않는다)."""
    details = deal.details
    row.name = details.name
    row.owner_user_id = details.owner_user_id
    row.vendor = details.vendor
    row.solution = details.solution
    row.users = details.users
    row.status_key = deal.sync.status_key
    row.forecast_key = deal.sync.forecast_key
    row.revenue_amount = details.revenue_amount.value
    row.revenue_date = details.revenue_date
    row.customer_id = deal.customer_id
    row.quote_submitted = details.quote.submitted.value if details.quote.submitted else None
    row.quote_submitted_date = details.quote.submitted_date
    row.poc_state = details.poc.state.value if details.poc.state else None
    row.poc_completed_date = details.poc.completed_date
    row.procurement = details.procurement
    row.updated_at = deal.updated_at


def new_row(deal: Deal) -> DealRow:
    row = DealRow(deal_code=deal.id.value, created_at=deal.created_at)
    apply_fields(row, deal)
    return row


def bant_pairs(deal: Deal) -> dict[str, BantLabelId]:
    """선택된 구분 -> Label id (선택 안 함은 빠진다)."""
    selected = {category.value: deal.bant.get(category) for category in BantCategory}
    return {category: label for category, label in selected.items() if label is not None}


def _bant_selection(rows: Iterable[DealBantLabelRow]) -> BantSelection:
    chosen = {row.category: BantLabelId(row.label_id) for row in rows}
    return BantSelection(
        budget=chosen.get(BantCategory.BUDGET.value),
        authority=chosen.get(BantCategory.AUTHORITY.value),
        need=chosen.get(BantCategory.NEED.value),
        timeline=chosen.get(BantCategory.TIMELINE.value),
    )


def _details(row: DealRow) -> DealDetails:
    return DealDetails(
        name=row.name,
        owner_user_id=UserId(row.owner_user_id),
        vendor=row.vendor,
        solution=row.solution,
        users=row.users,
        revenue_amount=RevenueAmount(int(row.revenue_amount)),
        revenue_date=row.revenue_date,
        quote=Quote(
            QuoteSubmitted(row.quote_submitted) if row.quote_submitted else None,
            row.quote_submitted_date,
        ),
        poc=Poc(PocState(row.poc_state) if row.poc_state else None, row.poc_completed_date),
        procurement=row.procurement,
    )


def to_entity(
    row: DealRow, partners: Iterable[DealPartnerRow], bant: Iterable[DealBantLabelRow]
) -> Deal:
    return Deal(
        id=DealCode(row.deal_code),
        details=_details(row),
        sync=SyncState(row.status_key, row.forecast_key),
        customer_id=ContactId(row.customer_id),
        partner_links=[
            PartnerLink(ContactId(link.contact_id), link.linked_at, link.unlinked_at)
            for link in partners
        ],
        bant=_bant_selection(bant),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
