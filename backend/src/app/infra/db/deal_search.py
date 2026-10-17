"""Deal 목록 질의: 조건, 정렬, 활동에서 파생되는 값(last_updated_at, next_action).

keyword·owner·vendor·solution·status·forecast·기간(연/분기 포함)·BANT Label 필터와 정렬 선택을
적용한다. 기간은 DealQuery.revenue_window()의 양끝 포함 범위다(빈 창이면 조건이 서로 모순되어 0건).
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import ColumnElement, collate, exists, func, or_, select

from app.application.ports.deal_repository import DealSort, SortOrder
from app.domain.code.values import CodeKind
from app.infra.db.like import LIKE_ESCAPE, like_pattern
from app.infra.db.models import DealActionRow
from app.infra.db.models_catalog import CodeRow
from app.infra.db.models_contact import ContactRow
from app.infra.db.models_deal import DealBantLabelRow, DealPartnerRow, DealRow

if TYPE_CHECKING:
    from datetime import date, datetime

    from sqlalchemy import Select

    from app.application.ports.deal_repository import DealQuery

# 목록 질의의 한 행: (Deal 행, last_updated_at, 최근 활동의 next_action, 최근 활동의 due_date)
# 최근 활동 outer join이라 활동이 없는 Deal은 next_action·due_date가 모두 NULL이다.
type ItemSelect = Select[tuple[DealRow, datetime, str | None, date | None]]

# 가장 최근 활동(acted_at, id 내림차순 첫 행)만 남기는 부분 질의.
_RANKED = select(
    DealActionRow.deal_code.label("deal_code"),
    DealActionRow.acted_at.label("acted_at"),
    DealActionRow.next_action.label("next_action"),
    DealActionRow.due_date.label("due_date"),
    func.row_number()
    .over(
        partition_by=DealActionRow.deal_code,
        order_by=(DealActionRow.acted_at.desc(), DealActionRow.id.desc()),
    )
    .label("position"),
).subquery("ranked_actions")
LATEST = select(_RANKED).where(_RANKED.c.position == 1).subquery("latest_action")

LAST_UPDATED = func.greatest(DealRow.updated_at, LATEST.c.acted_at)
_STATUS_ORDER = (
    select(CodeRow.sort_order)
    .where(CodeRow.kind == CodeKind.STATUS.value, CodeRow.key == DealRow.status_key)
    .scalar_subquery()
)


def _keyword_condition(keyword: str) -> ColumnElement[bool]:
    """Deal Name·Deal code·고객 회사·활성 파트너 회사의 대소문자 무시 부분 일치."""
    pattern = like_pattern(keyword)
    customer = exists().where(
        ContactRow.id == DealRow.customer_id, ContactRow.company.ilike(pattern, escape=LIKE_ESCAPE)
    )
    partner = exists().where(
        DealPartnerRow.deal_code == DealRow.deal_code,
        DealPartnerRow.unlinked_at.is_(None),
        DealPartnerRow.contact_id == ContactRow.id,
        ContactRow.company.ilike(pattern, escape=LIKE_ESCAPE),
    )
    return or_(
        DealRow.name.ilike(pattern, escape=LIKE_ESCAPE),
        DealRow.deal_code.ilike(pattern, escape=LIKE_ESCAPE),
        customer,
        partner,
    )


def conditions(query: DealQuery) -> list[ColumnElement[bool]]:
    """query의 조건을 AND로 결합할 WHERE 절 목록. 기간은 양끝을 포함한다."""
    found: list[ColumnElement[bool]] = []
    if query.keyword is not None:
        found.append(_keyword_condition(query.keyword))
    equals = (
        (DealRow.owner_user_id, query.owner_user_id),
        (DealRow.vendor, query.vendor),
        (DealRow.solution, query.solution),
        (DealRow.status_key, query.status_key),
        (DealRow.forecast_key, query.forecast_key),
    )
    found.extend(column == wanted for column, wanted in equals if wanted is not None)
    window_from, window_to = query.revenue_window()  # 연/분기와 revenue_from/to의 교집합
    if window_from is not None:
        found.append(DealRow.revenue_date >= window_from)
    if window_to is not None:
        found.append(DealRow.revenue_date <= window_to)
    found.extend(
        exists().where(
            DealBantLabelRow.deal_code == DealRow.deal_code,
            DealBantLabelRow.category == category.value,
            DealBantLabelRow.label_id == label_id,
        )
        for category, label_id in query.bant_label_ids.items()
    )
    return found


def item_select() -> ItemSelect:
    """Deal 행과 파생값(last_updated_at, 최근 활동의 next_action·due_date)."""
    return select(
        DealRow, LAST_UPDATED.label("last_updated_at"), LATEST.c.next_action, LATEST.c.due_date
    ).outerjoin_from(DealRow, LATEST, LATEST.c.deal_code == DealRow.deal_code)


def _sort_column(sort: DealSort) -> ColumnElement[Any]:
    columns: dict[DealSort, Any] = {
        DealSort.NAME: collate(func.lower(DealRow.name), "C"),
        DealSort.REVENUE_AMOUNT: DealRow.revenue_amount,
        DealSort.REVENUE_DATE: DealRow.revenue_date,
        DealSort.STATUS: _STATUS_ORDER,
        DealSort.LAST_UPDATED_AT: LAST_UPDATED,
    }
    column: ColumnElement[Any] = columns[sort]
    return column


def search_select(query: DealQuery) -> ItemSelect:
    """조건·정렬·페이지를 적용한 목록 질의. 정렬의 동률은 항상 Deal code 오름차순이다."""
    column = _sort_column(query.sort)
    ordered = column.desc() if query.order is SortOrder.DESC else column.asc()
    return (
        item_select()
        .where(*conditions(query))
        .order_by(ordered, DealRow.deal_code.asc())
        .offset(query.offset)
        .limit(query.limit)
    )
