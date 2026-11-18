"""Deal 목록 질의의 조건과 select. 파생값은 deal_derived, 정렬은 deal_list_order.

keyword·owner·vendor·product·status·forecast(여러 값 OR)·연/분기·최종 업데이트 기간·
Next Action 상태·기한초과/미업데이트 필터를 적용한다.
Expected Close 연/분기는 DealQuery.revenue_window()의 양끝 포함 범위에 revenue_quarters()의
분기 IN 조건을 AND로 더한다(Q1·Q3처럼 떨어진 분기를 정확히 거른다).
최종 업데이트 기간은 날짜 [updated_from, updated_to] 양끝 포함이며 상관 스칼라 서브쿼리로 비교한다.
기한초과·미업데이트는 compute_risk와 같은 판정이며 둘 다 켜면 OR, 종결(won·lost)은 제외한다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, and_, exists, extract, func, or_, select

from app.infra.db.deal_derived import (
    LAST_UPDATED,
    LATEST_ACTED,
    LATEST_NEXT,
    last_updated_scalar,
)
from app.infra.db.deal_list_order import order_clause
from app.infra.db.deal_risk import (
    earliest_open_due_scalar,
    not_closed_condition,
    overdue_condition,
    stale_condition,
)
from app.infra.db.like import LIKE_ESCAPE, like_pattern
from app.infra.db.models_catalog import CodeRow
from app.infra.db.models_comment import DealCommentRow
from app.infra.db.models_contact import ContactRow
from app.infra.db.models_deal import DealPartnerRow, DealRow
from app.infra.db.models_license_contract import ISSUED_STATUSES, LicenseContractRow

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy import Select

    from app.application.ports.deal_action_repository import NextActionStatusFilter
    from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
    from app.application.ports.deal_repository import DealQuery

# 목록 질의의 한 행: (Deal 행, last_updated_on, 기준 행의 next_action·due_date·상태, 계약 수)
# 기준 행 outer join이라 Next Action이 없는 Deal은 세 값이 모두 NULL이다.
type ItemSelect = Select[
    tuple[DealRow, date, str | None, date | None, str | None, date | None, int, int, bool]
]


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
        selected.append(overdue_condition(basis.today))
    if query.stale:
        selected.append(stale_condition(basis.stale_before()))
    return and_(not_closed_condition(), or_(*selected))


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
    """Expected Close 범위(양끝 포함)·분기 IN과 최종 업데이트 기간(날짜, 양끝 포함) 조건."""
    found: list[ColumnElement[bool]] = []
    window_from, window_to = query.revenue_window()  # 연/분기 범위
    if window_from is not None:
        found.append(DealRow.revenue_date >= window_from)
    if window_to is not None:
        found.append(DealRow.revenue_date <= window_to)
    quarters = query.revenue_quarters()  # 범위는 사이 분기를 포함하므로 분기로 다시 거른다
    if quarters is not None:
        found.append(extract("quarter", DealRow.revenue_date).in_(sorted(quarters)))
    if query.updated_from is not None:
        found.append(last_updated_scalar() >= query.updated_from)
    if query.updated_to is not None:
        found.append(last_updated_scalar() <= query.updated_to)
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
    if query.product is not None:
        found.append(DealRow.product.ilike(like_pattern(query.product), escape=LIKE_ESCAPE))
    found.extend(column == wanted for column, wanted in equals if wanted is not None)
    found.extend(_window_conditions(query))
    if query.wants_risk():
        found.append(_risk_condition(query))
    return found


def _contract_count() -> ColumnElement[int]:
    """이 Deal의 라이선스 계약 수(종료 포함). 상관 스칼라 서브쿼리라 조인 구조를 바꾸지 않는다."""
    return (
        select(func.count(LicenseContractRow.id))
        .where(LicenseContractRow.deal_id == DealRow.id)
        .correlate(DealRow)
        .scalar_subquery()
    )


def _unread_comment_count() -> ColumnElement[int]:
    """이 Deal의 읽지 않은 Comment 수(read_at IS NULL, 부분 인덱스 사용)."""
    return (
        select(func.count(DealCommentRow.id))
        .where(DealCommentRow.deal_id == DealRow.id, DealCommentRow.read_at.is_(None))
        .correlate(DealRow)
        .scalar_subquery()
    )


def _has_issued_contract() -> ColumnElement[bool]:
    """이 Deal에 발급 상태(신규·갱신) 라이선스 계약이 있는지."""
    return (
        select(LicenseContractRow.id)
        .where(
            LicenseContractRow.deal_id == DealRow.id,
            LicenseContractRow.status.in_(ISSUED_STATUSES),
        )
        .correlate(DealRow)
        .exists()
    )


def item_select() -> ItemSelect:
    """Deal 행과 파생값.

    최종 업데이트일, 기준 행의 Next Action·Due·상태, 가장 이른 Open Due,
    계약 수·읽지 않은 Comment 수, 발급 계약 여부.
    """
    return (
        select(
            DealRow,
            LAST_UPDATED.label("last_updated_on"),
            LATEST_NEXT.c.next_action,
            LATEST_NEXT.c.due_date,
            LATEST_NEXT.c.next_action_status.label("basis_status"),
            earliest_open_due_scalar().label("earliest_open_due"),
            _contract_count().label("license_contract_count"),
            _unread_comment_count().label("unread_comment_count"),
            _has_issued_contract().label("has_issued_license_contract"),
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
