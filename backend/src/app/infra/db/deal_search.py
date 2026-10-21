"""Deal 목록 질의: 조건, 정렬, 활동에서 파생되는 값(last_updated_at, next_action).

last_updated_at = 모든 Action 중 가장 최근 acted_at(없으면 Deal 등록 시각, Deal 수정은 무시).
next_action 요약과 상태 필터의 기준 행 = Next Action이 있는 가장 최근 Action.

keyword·owner·vendor·solution·status·forecast·연/분기·최종 업데이트 기간·BANT Label 필터와
정렬 선택을 적용한다.
Expected Close 연/분기는 DealQuery.revenue_window()의 양끝 포함 범위다.
최종 업데이트 기간은 updated_window()의 반개구간 [시작, 끝)이며 상관 스칼라 서브쿼리로 비교한다.
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

# 목록 질의의 한 행: (Deal 행, last_updated_at, 기준 행의 next_action·due_date·상태)
# 기준 행 outer join이라 Next Action이 없는 Deal은 세 값이 모두 NULL이다.
type ItemSelect = Select[tuple[DealRow, datetime, str | None, date | None, str | None]]

# Deal별 모든 Action 중 가장 최근 수행 시각(진행사항만 있는 행 포함).
LATEST_ACTED = (
    select(
        DealActionRow.deal_id.label("deal_id"),
        func.max(DealActionRow.acted_at).label("acted_at"),
    )
    .group_by(DealActionRow.deal_id)
    .subquery("latest_acted")
)

# Next Action이 있는 Action 중 가장 최근 행(acted_at, id 내림차순 첫 행)만 남기는 부분 질의.
_RANKED = (
    select(
        DealActionRow.deal_id.label("deal_id"),
        DealActionRow.next_action.label("next_action"),
        DealActionRow.due_date.label("due_date"),
        DealActionRow.next_action_status.label("next_action_status"),
        func.row_number()
        .over(
            partition_by=DealActionRow.deal_id,
            order_by=(DealActionRow.acted_at.desc(), DealActionRow.id.desc()),
        )
        .label("position"),
    )
    .where(DealActionRow.next_action.is_not(None))
    .subquery("ranked_next_actions")
)
LATEST_NEXT = select(_RANKED).where(_RANKED.c.position == 1).subquery("latest_next_action")

LAST_UPDATED = func.coalesce(LATEST_ACTED.c.acted_at, DealRow.created_at)
_STATUS_ORDER = (
    select(CodeRow.sort_order)
    .where(CodeRow.kind == CodeKind.STATUS.value, CodeRow.key == DealRow.status_key)
    .scalar_subquery()
)


def _last_updated_scalar() -> ColumnElement[datetime]:
    """LAST_UPDATED와 같은 값을 조인 없이 계산하는 상관 스칼라 서브쿼리(count가 조건만 쓴다)."""
    latest = (
        select(func.max(DealActionRow.acted_at))
        .where(DealActionRow.deal_id == DealRow.id)
        .correlate(DealRow)
        .scalar_subquery()
    )
    return func.coalesce(latest, DealRow.created_at)


def _keyword_condition(keyword: str) -> ColumnElement[bool]:
    """Deal Name·Deal code·고객 회사·활성 파트너 회사의 대소문자 무시 부분 일치."""
    pattern = like_pattern(keyword)
    customer = exists().where(
        ContactRow.id == DealRow.customer_id, ContactRow.company.ilike(pattern, escape=LIKE_ESCAPE)
    )
    partner = exists().where(
        DealPartnerRow.deal_id == DealRow.id,
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
        (DealRow.vendor_id, query.vendor_id),
        (DealRow.solution_id, query.solution_id),
        (DealRow.status_key, query.status_key),
        (DealRow.forecast_key, query.forecast_key),
    )
    if query.next_action_status is not None:
        wanted_statuses = [status.value for status in query.next_action_status.statuses()]
        found.append(
            select(LATEST_NEXT.c.deal_id)
            .where(
                LATEST_NEXT.c.deal_id == DealRow.id,
                LATEST_NEXT.c.next_action_status.in_(wanted_statuses),
            )
            .correlate(DealRow)
            .exists()
        )
    found.extend(column == wanted for column, wanted in equals if wanted is not None)
    window_from, window_to = query.revenue_window()  # 연/분기 범위
    if window_from is not None:
        found.append(DealRow.revenue_date >= window_from)
    if window_to is not None:
        found.append(DealRow.revenue_date <= window_to)
    updated_start, updated_end = query.updated_window()
    if updated_start is not None:
        found.append(_last_updated_scalar() >= updated_start)
    if updated_end is not None:
        found.append(_last_updated_scalar() < updated_end)
    found.extend(
        exists().where(
            DealBantLabelRow.deal_id == DealRow.id,
            DealBantLabelRow.category == category.value,
            DealBantLabelRow.label_id == label_id,
        )
        for category, label_id in query.bant_label_ids.items()
    )
    return found


def item_select() -> ItemSelect:
    """Deal 행과 파생값(last_updated_at, 기준 행의 next_action·due_date·상태)."""
    return (
        select(
            DealRow,
            LAST_UPDATED.label("last_updated_at"),
            LATEST_NEXT.c.next_action,
            LATEST_NEXT.c.due_date,
            LATEST_NEXT.c.next_action_status.label("basis_status"),
        )
        .outerjoin_from(DealRow, LATEST_ACTED, LATEST_ACTED.c.deal_id == DealRow.id)
        .outerjoin_from(DealRow, LATEST_NEXT, LATEST_NEXT.c.deal_id == DealRow.id)
    )


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
