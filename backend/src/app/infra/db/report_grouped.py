"""그룹핑 리포트의 SQL. 안쪽 하위 쿼리(base)에서 식을 한 번씩 계산하고 바깥에서 집계한다.

안쪽에서 식을 한 번만 계산하면 SELECT·GROUP BY의 식이 어긋나지 않는다(바인딩 파라미터 포함).
행 범위가 Action이면 Deal 단위 값(금액·Users·Status 체류 일수의 합계·평균, Deal 필드의 건수)은
`row_number() OVER (PARTITION BY <그룹 키>, deals.id)`의 첫 행만 세어 그룹마다 Deal당 한 번 센다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import case, distinct, func, null, select

from app.domain.report.vocabulary import Aggregate, Entity
from app.infra.db.report_fields import direction_order
from app.infra.db.report_joins import ACTIONS, DEALS

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement, Label, Select, Subquery

    from app.domain.report.definition import ReportColumn
    from app.infra.db.report_fields import Expr
    from app.infra.db.report_parts import ReportParts

_RANK = "deal_rank"
_TOTAL_COUNT = "total_count"


class _InnerColumns:
    """안쪽 하위 쿼리의 열. 같은 식 객체는 한 열만 만든다."""

    def __init__(self) -> None:
        self.labels: list[Label[Any]] = []
        self._names: dict[int, str] = {}

    def add(self, expr: Expr) -> str:
        found = self._names.get(id(expr))
        if found is not None:
            return found
        name = f"i{len(self.labels)}"
        self.labels.append(expr.label(name))
        self._names[id(expr)] = name
        return name


@dataclass(frozen=True, slots=True)
class _GroupNames:
    key: str
    value: str
    order: str


@dataclass(frozen=True, slots=True)
class _Plan:
    """컬럼별 안쪽 열 이름: 그룹 컬럼이면 group, 아니면 measure."""

    column: ReportColumn
    group: _GroupNames | None
    measure: str | None


def _plan_columns(
    parts: ReportParts, inner: _InnerColumns, *, with_groups: bool
) -> tuple[list[_Plan], list[Expr]]:
    """안쪽 열을 등록한다. with_groups가 거짓(합계)이면 그룹 컬럼은 안쪽에 필요 없다."""
    plans: list[_Plan] = []
    keys: list[Expr] = []
    for column in parts.definition.columns:
        if column.group:
            if with_groups:
                exprs = parts.group_exprs(column)
                names = _GroupNames(
                    inner.add(exprs.key), inner.add(exprs.value), inner.add(exprs.order)
                )
                keys.append(exprs.key)
                plans.append(_Plan(column, names, None))
            else:
                plans.append(_Plan(column, None, None))
        else:
            plans.append(_Plan(column, None, inner.add(parts.measure(column))))
    return plans, keys


def _base(parts: ReportParts, inner: _InnerColumns, partition: list[Expr]) -> Subquery:
    """FROM/JOIN/WHERE를 적용한 안쪽 하위 쿼리. Action 행 범위면 Deal당 순번 열을 더한다."""
    columns: list[Label[Any]] = [*inner.labels, DEALS.c.id.label("deal_id")]
    if parts.is_action_scope():
        rank = func.row_number().over(partition_by=[*partition, DEALS.c.id], order_by=ACTIONS.c.id)
        columns.append(rank.label(_RANK))
    where = parts.where()
    statement = select(*columns)
    if where is not None:
        statement = statement.where(where)
    return statement.select_from(parts.source()).subquery("base")


def _aggregate(
    column: ReportColumn, ref: ColumnElement[Any], base: Subquery, *, ranked: bool
) -> Expr:
    """집계식. Action 행 범위의 Deal 필드(합계·평균·건수)는 Deal당 한 번만 센다."""
    once = ranked and column.field.entity is Entity.DEAL
    first_only = case((base.c[_RANK] == 1, ref)) if once else ref
    match column.aggregate:
        case Aggregate.SUM:
            return func.sum(first_only)
        case Aggregate.AVG:
            return func.avg(first_only)
        case Aggregate.MIN:
            return func.min(ref)
        case Aggregate.MAX:
            return func.max(ref)
        case Aggregate.COUNT:
            return func.count(first_only)
        case Aggregate.COUNT_DISTINCT:
            return func.count(distinct(ref))
    raise ValueError(f"집계가 필요합니다: {column.field.key}")


def _order_by(
    parts: ReportParts, plans: list[_Plan], base: Subquery, outer: list[Label[Any]]
) -> list[Any]:
    """지정한 정렬들(컬럼 순서) -> 그룹 컬럼의 정렬 식 -> 그룹 키(동률 해소). 같은 열은 한 번만."""
    order: list[Any] = []
    seen: set[str] = set()
    for sort in parts.definition.sort_keys():
        picked = plans[sort.column]
        if picked.group is None:
            order.append(direction_order(outer[sort.column], sort.direction))
        elif picked.group.order not in seen:
            seen.add(picked.group.order)
            order.append(direction_order(base.c[picked.group.order], sort.direction))
    for plan in plans:
        if plan.group is None:
            continue
        for name in (plan.group.order, plan.group.key):
            if name not in seen:
                seen.add(name)
                order.append(base.c[name].asc().nulls_last())
    return order


def grouped_select(parts: ReportParts) -> Select[Any]:
    """그룹별 한 행. 마지막 열 total_count는 그룹 수(행 수 제한 전)."""
    inner = _InnerColumns()
    plans, keys = _plan_columns(parts, inner, with_groups=True)
    base = _base(parts, inner, keys)
    outer: list[Label[Any]] = []
    group_by: list[Any] = []
    for index, plan in enumerate(plans):
        if plan.group is not None:
            outer.append(base.c[plan.group.value].label(f"c{index}"))
            group_by.extend(
                base.c[name] for name in (plan.group.key, plan.group.value, plan.group.order)
            )
        elif plan.measure is not None:
            outer.append(
                _aggregate(
                    plan.column, base.c[plan.measure], base, ranked=parts.is_action_scope()
                ).label(f"c{index}")
            )
    order = _order_by(parts, plans, base, outer)
    return (
        select(*outer, func.count().over().label(_TOTAL_COUNT))
        .group_by(*dict.fromkeys(group_by))
        .order_by(*order)
        .limit(parts.definition.row_limit)
    )


def grouped_totals_select(parts: ReportParts) -> Select[Any]:
    """그룹 없이 같은 조건의 전체 범위를 집계한 한 행(그룹 컬럼은 NULL, Deal은 한 번만 센다)."""
    inner = _InnerColumns()
    plans, _ = _plan_columns(parts, inner, with_groups=False)
    base = _base(parts, inner, [])
    outer: list[Label[Any]] = []
    for index, plan in enumerate(plans):
        if plan.measure is None:
            outer.append(null().label(f"c{index}"))
        else:
            outer.append(
                _aggregate(
                    plan.column, base.c[plan.measure], base, ranked=parts.is_action_scope()
                ).label(f"c{index}")
            )
    return select(*outer).select_from(base)
