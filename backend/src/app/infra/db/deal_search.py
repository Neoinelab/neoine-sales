"""Deal 목록 질의의 조건과 select. 파생값은 deal_derived, 정렬은 deal_list_order.

keyword·owner·vendor·solution·status·forecast(여러 값 OR)·연/분기·최종 업데이트 기간·
Next Action 상태·기한초과/미업데이트 필터를 적용한다.
Expected Close 연/분기는 DealQuery.revenue_window()의 양끝 포함 범위다.
최종 업데이트 기간은 updated_window()의 반개구간 [시작, 끝)이며 상관 스칼라 서브쿼리로 비교한다.
기한초과·미업데이트는 compute_risk와 같은 판정이며 둘 다 켜면 OR, 종결(won·lost)은 제외한다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, and_, exists, or_, select

from app.domain.deal.sync_state import CLOSED_FORECASTS
from app.infra.db.deal_derived import (
    LAST_UPDATED,
    LATEST_ACTED,
    LATEST_NEXT,
    last_updated_scalar,
)
from app.infra.db.deal_list_order import order_clause
from app.infra.db.like import LIKE_ESCAPE, like_pattern
from app.infra.db.models_catalog import CodeRow
from app.infra.db.models_contact import ContactRow
from app.infra.db.models_deal import DealPartnerRow, DealRow

if TYPE_CHECKING:
    from datetime import date, datetime

    from sqlalchemy import Select

    from app.application.ports.deal_action_repository import NextActionStatusFilter
    from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
    from app.application.ports.deal_repository import DealQuery

# 목록 질의의 한 행: (Deal 행, last_updated_at, 기준 행의 next_action·due_date·상태)
# 기준 행 outer join이라 Next Action이 없는 Deal은 세 값이 모두 NULL이다.
type ItemSelect = Select[tuple[DealRow, datetime, str | None, date | None, str | None]]


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


def _risk_condition(query: DealQuery) -> ColumnElement[bool]:
    """기한초과/미업데이트(OR) 조건. 종결(won·lost) Deal은 제외한다. basis가 없으면 ValueError."""
    basis = query.risk_basis
    if basis is None:
        raise ValueError("기한초과·미업데이트 필터에는 risk_basis가 필요합니다.")
    selected: list[ColumnElement[bool]] = []
    if query.overdue:
        selected.append(
            select(LATEST_NEXT.c.deal_id)
            .where(LATEST_NEXT.c.deal_id == DealRow.id, LATEST_NEXT.c.due_date < basis.today)
            .correlate(DealRow)
            .exists()
        )
    if query.stale:
        selected.append(last_updated_scalar() < basis.stale_before())
    return and_(DealRow.forecast_key.not_in(sorted(CLOSED_FORECASTS)), or_(*selected))


def _outcome_condition(outcome: ForecastOutcomeFilter) -> ColumnElement[bool]:
    """Forecast 코드의 outcome이 필터에 속하는 Deal(forecast_keys 조건과 AND로 결합된다)."""
    wanted = [item.value for item in outcome.outcomes()]
    return (
        select(CodeRow.id)
        .where(
            CodeRow.kind == DealRow.forecast_kind,
            CodeRow.key == DealRow.forecast_key,
            CodeRow.outcome.in_(wanted),
        )
        .correlate(DealRow)
        .exists()
    )


def _next_action_condition(statuses: NextActionStatusFilter) -> ColumnElement[bool]:
    """기준 Next Action 행의 상태가 필터에 속하는 Deal."""
    wanted = [status.value for status in statuses.statuses()]
    return (
        select(LATEST_NEXT.c.deal_id)
        .where(LATEST_NEXT.c.deal_id == DealRow.id, LATEST_NEXT.c.next_action_status.in_(wanted))
        .correlate(DealRow)
        .exists()
    )


def _window_conditions(query: DealQuery) -> list[ColumnElement[bool]]:
    """Expected Close 범위(양끝 포함)와 최종 업데이트 기간([시작, 끝)) 조건."""
    found: list[ColumnElement[bool]] = []
    window_from, window_to = query.revenue_window()  # 연/분기 범위
    if window_from is not None:
        found.append(DealRow.revenue_date >= window_from)
    if window_to is not None:
        found.append(DealRow.revenue_date <= window_to)
    updated_start, updated_end = query.updated_window()
    if updated_start is not None:
        found.append(last_updated_scalar() >= updated_start)
    if updated_end is not None:
        found.append(last_updated_scalar() < updated_end)
    return found


def conditions(query: DealQuery) -> list[ColumnElement[bool]]:
    """query의 조건을 AND로 결합할 WHERE 절 목록. 기간은 양끝을 포함한다."""
    found: list[ColumnElement[bool]] = []
    if query.keyword is not None:
        found.append(_keyword_condition(query.keyword))
    equals = (
        (DealRow.owner_user_id, query.owner_user_id),
        (DealRow.vendor_id, query.vendor_id),
        (DealRow.status_key, query.status_key),
    )
    if query.forecast_keys is not None:
        found.append(DealRow.forecast_key.in_(sorted(query.forecast_keys)))
    if query.forecast_outcome is not None:
        found.append(_outcome_condition(query.forecast_outcome))
    if query.next_action_status is not None:
        found.append(_next_action_condition(query.next_action_status))
    if query.solution is not None:
        found.append(DealRow.solution.ilike(like_pattern(query.solution), escape=LIKE_ESCAPE))
    found.extend(column == wanted for column, wanted in equals if wanted is not None)
    found.extend(_window_conditions(query))
    if query.wants_risk():
        found.append(_risk_condition(query))
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


def search_select(query: DealQuery) -> ItemSelect:
    """조건·정렬·페이지를 적용한 목록 질의. 정렬의 동률은 항상 Deal code 오름차순이다."""
    return (
        item_select()
        .where(*conditions(query))
        .order_by(*order_clause(query.sort, query.order))
        .offset(query.offset)
        .limit(query.limit)
    )
