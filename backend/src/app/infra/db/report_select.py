"""리포트 SQL 생성의 진입점. 그룹핑이 없으면 값 식을 그대로 고르고, 있으면 report_grouped로 넘긴다.

모든 사용자 값은 바인딩 파라미터이고 식별자는 카탈로그 화이트리스트(필드 레지스트리)에서만 온다.
정렬은 항상 NULL을 뒤로 보내고, 동률은 Deal code(Action 행이면 수행일시·id)로 가른다.
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.infra.db.report_fields import direction_order
from app.infra.db.report_grouped import grouped_select, grouped_totals_select
from app.infra.db.report_joins import ACTIONS, DEALS
from app.infra.db.report_parts import ReportParts

if TYPE_CHECKING:
    from sqlalchemy import Select

    from app.domain.report.resolve import ResolvedReport

TOTAL_COUNT_LABEL = "total_count"


def _plain_select(parts: ReportParts) -> Select[Any]:
    definition = parts.definition
    values = [parts.value_of(column).label(f"c{i}") for i, column in enumerate(definition.columns)]
    order = []
    seen: set[int] = set()
    for sort in definition.sort_keys():
        expr = parts.field(definition.columns[sort.column].field).order
        if id(expr) not in seen:
            seen.add(id(expr))
            order.append(direction_order(expr, sort.direction))
    order.append(DEALS.c.deal_code.asc())
    if parts.is_action_scope():
        order.extend([ACTIONS.c.acted_at.asc(), ACTIONS.c.id.asc()])
    where = parts.where()
    statement = select(*values, func.count().over().label(TOTAL_COUNT_LABEL))
    if where is not None:
        statement = statement.where(where)
    return statement.select_from(parts.source()).order_by(*order).limit(definition.row_limit)


def build_select(report: ResolvedReport) -> Select[Any]:
    """데이터 문장: 컬럼 순서의 값들 + 마지막 열 total_count(행 수 제한 전 전체 행/그룹 수)."""
    parts = ReportParts(report)
    if parts.definition.is_grouped():
        return grouped_select(parts)
    return _plain_select(parts)


def build_totals_select(report: ResolvedReport) -> Select[Any] | None:
    """그룹핑이고 집계 컬럼이 있을 때만: 같은 조건을 그룹 없이 한 번 더 집계한 한 행."""
    parts = ReportParts(report)
    definition = parts.definition
    if not definition.is_grouped() or all(column.group for column in definition.columns):
        return None
    return grouped_totals_select(parts)
