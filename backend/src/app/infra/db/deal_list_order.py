"""Deal 목록의 정렬. 모든 정렬은 상관 스칼라 서브쿼리라 조인 구조(count 포함)를 바꾸지 않는다.

텍스트 키는 소문자·COLLATE "C"(코드 포인트 순). 값이 없는 Deal(파트너·Vendor)은 방향과 무관하게
맨 뒤이고, 동률은 방향과 무관하게 Deal code 오름차순이다.
"""

from typing import Any

from sqlalchemy import ColumnElement, SQLColumnExpression, collate, func, select

from app.application.ports.deal_repository import DealSort, SortOrder
from app.domain.code.values import CodeKind
from app.infra.db.deal_derived import LAST_UPDATED
from app.infra.db.models_auth import UserRow
from app.infra.db.models_catalog import CodeRow, VendorRow
from app.infra.db.models_contact import ContactRow
from app.infra.db.models_deal import DealPartnerRow, DealRow


def _text_key(column: SQLColumnExpression[str]) -> ColumnElement[str]:
    return collate(func.lower(column), "C")


def _code_order(kind: CodeKind, key: SQLColumnExpression[str]) -> ColumnElement[int]:
    return (
        select(CodeRow.sort_order).where(CodeRow.kind == kind.value, CodeRow.key == key)
    ).scalar_subquery()


def _owner_key() -> ColumnElement[str]:
    name = func.coalesce(func.nullif(UserRow.display_name, ""), UserRow.login_id)
    return select(_text_key(name)).where(UserRow.id == DealRow.owner_user_id).scalar_subquery()


def _customer_key() -> ColumnElement[str]:
    company = select(_text_key(ContactRow.company)).where(ContactRow.id == DealRow.customer_id)
    return company.scalar_subquery()


def _partner_key() -> ColumnElement[str]:
    """활성(해제되지 않은) 파트너 회사명. 활성 파트너는 Deal당 최대 1개다."""
    return (
        select(_text_key(ContactRow.company))
        .where(
            DealPartnerRow.deal_id == DealRow.id,
            DealPartnerRow.unlinked_at.is_(None),
            DealPartnerRow.contact_id == ContactRow.id,
        )
        .scalar_subquery()
    )


def _vendor_key() -> ColumnElement[str]:
    name = select(_text_key(VendorRow.name)).where(VendorRow.id == DealRow.vendor_id)
    return name.scalar_subquery()


def _sort_column(sort: DealSort) -> ColumnElement[Any]:
    columns: dict[DealSort, Any] = {
        DealSort.NAME: lambda: _text_key(DealRow.name),
        DealSort.REVENUE_AMOUNT: lambda: DealRow.revenue_amount,
        DealSort.REVENUE_DATE: lambda: DealRow.revenue_date,
        DealSort.STATUS: lambda: _code_order(CodeKind.STATUS, DealRow.status_key),
        DealSort.LAST_UPDATED_AT: lambda: LAST_UPDATED,
        DealSort.OWNER: _owner_key,
        DealSort.CUSTOMER: _customer_key,
        DealSort.PARTNER: _partner_key,
        DealSort.VENDOR: _vendor_key,
        DealSort.FORECAST: lambda: _code_order(CodeKind.FORECAST, DealRow.forecast_key),
    }
    column: ColumnElement[Any] = columns[sort]()
    return column


def order_clause(sort: DealSort, order: SortOrder) -> tuple[ColumnElement[Any], ...]:
    """ORDER BY 절 목록: 선택 열(NULL은 항상 마지막)과 Deal code 오름차순 동률 규칙."""
    column = _sort_column(sort)
    ordered = column.desc() if order is SortOrder.DESC else column.asc()
    return (ordered.nulls_last(), DealRow.deal_code.asc())
