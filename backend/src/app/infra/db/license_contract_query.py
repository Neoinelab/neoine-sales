"""라이선스 계약 목록 질의: Deal 값을 함께 읽는 select, 조건, 정렬.

정렬은 주 키를 방향대로, 값 없는 칸은 방향과 무관하게 맨 뒤, 동률은 id 오름차순이다.
텍스트 키는 lower(...) COLLATE "C", 빈 문자열(제품·기술담당·Note)은 값 없음으로 본다.
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import ColumnElement, Select, SQLColumnExpression, case, collate, func, select
from sqlalchemy.orm import aliased

from app.application.ports.deal_repository import SortOrder
from app.application.ports.license_contract_repository import LicenseContractSort
from app.domain.license_contract.values import ContractStatus, InspectionCycle
from app.infra.db.like import LIKE_ESCAPE, like_pattern
from app.infra.db.models_auth import UserRow
from app.infra.db.models_catalog import VendorRow
from app.infra.db.models_contact import ContactRow
from app.infra.db.models_deal import DealPartnerRow, DealRow
from app.infra.db.models_license_contract import (
    LicenseContractAttachmentRow,
    LicenseContractRow,
)

if TYPE_CHECKING:
    from app.application.ports.license_contract_repository import LicenseContractQuery

_CUSTOMER = aliased(ContactRow)
_OWNER = aliased(UserRow)
_PARTNER = (
    select(ContactRow.company)
    .join(DealPartnerRow, DealPartnerRow.contact_id == ContactRow.id)
    .where(DealPartnerRow.deal_id == DealRow.id, DealPartnerRow.unlinked_at.is_(None))
    .correlate(DealRow)
    .scalar_subquery()
)
_ATTACHMENTS = (
    select(func.count(LicenseContractAttachmentRow.id))
    .where(LicenseContractAttachmentRow.contract_id == LicenseContractRow.id)
    .correlate(LicenseContractRow)
    .scalar_subquery()
)
_STATUS_ORDER = list(ContractStatus)
_INSPECTION_ORDER = [
    InspectionCycle.MONTHLY,
    InspectionCycle.QUARTERLY,
    InspectionCycle.SEMIANNUAL,
    InspectionCycle.YEARLY,
    InspectionCycle.NONE,
]


def row_select() -> Select[Any]:
    """계약 행과 Deal 값(고객·Vendor·제품·파트너·Owner)·첨부 수."""
    return (
        select(
            LicenseContractRow,
            DealRow.deal_code,
            DealRow.name.label("deal_name"),
            DealRow.solution,
            DealRow.owner_user_id,
            DealRow.forecast_key,
            _CUSTOMER.company.label("customer"),
            VendorRow.id.label("vendor_id"),
            VendorRow.name.label("vendor_name"),
            _PARTNER.label("partner"),
            _ATTACHMENTS.label("attachment_count"),
        )
        .join(DealRow, DealRow.id == LicenseContractRow.deal_id)
        .join(_CUSTOMER, _CUSTOMER.id == DealRow.customer_id)
        .outerjoin(VendorRow, VendorRow.id == DealRow.vendor_id)
        .join(_OWNER, _OWNER.id == DealRow.owner_user_id)
        .execution_options(populate_existing=True)
    )


def conditions(query: LicenseContractQuery) -> list[ColumnElement[bool]]:
    found: list[ColumnElement[bool]] = []
    if query.customer is not None:
        found.append(_CUSTOMER.company.ilike(like_pattern(query.customer), escape=LIKE_ESCAPE))
    if query.product is not None:
        found.append(DealRow.solution.ilike(like_pattern(query.product), escape=LIKE_ESCAPE))
    if query.vendor_id is not None:
        found.append(DealRow.vendor_id == query.vendor_id)
    if query.owner_user_id is not None:
        found.append(DealRow.owner_user_id == query.owner_user_id)
    if query.status is not None:
        found.append(LicenseContractRow.status == query.status.value)
    bounds = (
        (LicenseContractRow.license_start, query.start_from, query.start_to),
        (LicenseContractRow.license_end, query.end_from, query.end_to),
    )
    for column, low, high in bounds:
        if low is not None:
            found.append(column >= low)
        if high is not None:
            found.append(column <= high)
    return found


def count_select(query: LicenseContractQuery) -> Select[Any]:
    return (
        select(func.count(LicenseContractRow.id))
        .join(DealRow, DealRow.id == LicenseContractRow.deal_id)
        .join(_CUSTOMER, _CUSTOMER.id == DealRow.customer_id)
        .where(*conditions(query))
    )


def _text(column: SQLColumnExpression[Any], *, blank_is_none: bool = False) -> ColumnElement[Any]:
    key = func.lower(column)
    return collate(func.nullif(key, "") if blank_is_none else key, "C")


def _ranked(column: SQLColumnExpression[Any], order: list[Any]) -> ColumnElement[int]:
    return case({member.value: rank for rank, member in enumerate(order)}, value=column)


def _sort_expression(sort: LicenseContractSort) -> SQLColumnExpression[Any]:
    owner = func.coalesce(func.nullif(_OWNER.display_name, ""), _OWNER.login_id)
    keys: dict[LicenseContractSort, SQLColumnExpression[Any]] = {
        LicenseContractSort.DEAL_CODE: _text(DealRow.deal_code),
        LicenseContractSort.DEAL_NAME: _text(DealRow.name, blank_is_none=True),
        LicenseContractSort.CUSTOMER: _text(_CUSTOMER.company),
        LicenseContractSort.VENDOR: _text(VendorRow.name),
        LicenseContractSort.PRODUCT: _text(DealRow.solution, blank_is_none=True),
        LicenseContractSort.PARTNER: _text(_PARTNER),
        LicenseContractSort.LICENSE_START: LicenseContractRow.license_start,
        LicenseContractSort.LICENSE_END: LicenseContractRow.license_end,
        LicenseContractSort.STATUS: _ranked(LicenseContractRow.status, _STATUS_ORDER),
        LicenseContractSort.SALES_OWNER: _text(owner),
        LicenseContractSort.TECH_OWNER: _text(LicenseContractRow.tech_owner, blank_is_none=True),
        LicenseContractSort.INSPECTION: _ranked(
            LicenseContractRow.inspection_cycle, _INSPECTION_ORDER
        ),
        LicenseContractSort.NOTE: _text(LicenseContractRow.note, blank_is_none=True),
    }
    return keys[sort]


def search_select(query: LicenseContractQuery) -> Select[Any]:
    key = _sort_expression(query.sort)
    primary = key.asc() if query.order is SortOrder.ASC else key.desc()
    return (
        row_select()
        .where(*conditions(query))
        .order_by(primary.nulls_last(), LicenseContractRow.id)
        .offset(query.offset)
        .limit(query.limit)
    )
