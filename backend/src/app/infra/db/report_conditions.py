"""조건 -> SQL WHERE. 값은 모두 바인딩 파라미터이고 식별자는 필드 레지스트리에서만 얻는다.

Action 조건이 Deal 행 범위에서 쓰이면(`ActionFilter.EXISTS`) 모든 Action 조건을 EXISTS 하나에
묶는다: AND면 한 Action이 모두 만족, OR이면 Action 조건끼리 OR.
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    and_,
    exists,
    func,
    literal,
    literal_column,
    not_,
    or_,
    select,
    true,
)

from app.domain.report.condition_values import (
    IdList,
    KeyList,
    NoValue,
    NumberRange,
    NumberValue,
    TextValue,
)
from app.domain.report.definition import ActionFilter
from app.domain.report.resolve import DateBounds, DateTimeBounds
from app.domain.report.vocabulary import Combine, Entity, FieldType, Operator
from app.infra.db.like import LIKE_ESCAPE, like_pattern, like_prefix_pattern
from app.infra.db.report_joins import ACTIONS, DEALS

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.domain.report.fields import FieldSpec
    from app.domain.report.resolve import ResolvedCondition, ResolvedReport
    from app.infra.db.report_fields import Expr, FieldSql
    from app.infra.db.report_risk import RiskExprs

_RISK_KEY = "deal.risk"
_COMPARISONS: dict[Operator, Callable[[Expr, Expr], Expr]] = {
    Operator.EQ: lambda key, n: key == n,
    Operator.NE: lambda key, n: key != n,
    Operator.GT: lambda key, n: key > n,
    Operator.GTE: lambda key, n: key >= n,
    Operator.LT: lambda key, n: key < n,
    Operator.LTE: lambda key, n: key <= n,
}


def _big(n: int) -> Expr:
    """int4 열과 비교해도 범위 오류가 없도록 bigint로 바인딩한다."""
    return literal(n, BigInteger)


def _text(key: Expr, operator: Operator, text: str) -> Expr:
    match operator:
        case Operator.CONTAINS:
            return key.ilike(like_pattern(text), escape=LIKE_ESCAPE)
        case Operator.STARTS_WITH:
            return key.ilike(like_prefix_pattern(text), escape=LIKE_ESCAPE)
        case Operator.EQUALS:
            return func.lower(key) == func.lower(literal(text))
    raise ValueError(f"텍스트 연산자가 아닙니다: {operator}")


def _members(key: Expr, operator: Operator, values: list[str] | list[int]) -> Expr:
    """in / not_in. not_in은 값이 없는(NULL) 행을 포함한다."""
    if operator is Operator.IN:
        return key.in_(values)
    return or_(key.is_(None), key.not_in(values))


def _no_value(key: Expr, operator: Operator, field_type: FieldType) -> Expr:
    if field_type is FieldType.TEXT:
        empty = or_(key.is_(None), key == literal(""))
        return empty if operator is Operator.IS_EMPTY else not_(empty)
    return key.is_(None)


def _date_range(key: Expr, bounds: DateBounds) -> Expr:
    parts = []
    if bounds.first is not None:
        parts.append(key >= bounds.first)
    if bounds.last is not None:
        parts.append(key <= bounds.last)
    return and_(*parts) if parts else true()


def _instant_range(key: Expr, bounds: DateTimeBounds) -> Expr:
    parts = []
    if bounds.start is not None:
        parts.append(key >= bounds.start)
    if bounds.end is not None:
        parts.append(key < bounds.end)
    return and_(*parts) if parts else true()


def _risk(keys: KeyList | NoValue, operator: Operator, risk: RiskExprs) -> Expr:
    """경고 조건: Deals 목록 필터와 같은 뜻(종결 제외, 기한초과·미업데이트는 OR)."""
    if isinstance(keys, NoValue):
        return not_(risk.flagged({"overdue", "stale"}))
    flagged = risk.flagged(set(keys.keys))
    return flagged if operator is Operator.IN else not_(flagged)


def _discrete_clause(key: Expr, spec: FieldSpec, operator: Operator, value: object) -> Expr | None:
    """텍스트·목록·값 없음 조건. 해당하지 않으면 None."""
    match value:
        case TextValue(text):
            return _text(key, operator, text)
        case NoValue():
            return _no_value(key, operator, spec.type)
        case KeyList(keys):
            return _members(key, operator, list(keys))
        case IdList(ids):
            return _members(key, operator, list(ids))
    return None


def _range_clause(key: Expr, operator: Operator, value: object) -> Expr | None:
    """숫자·날짜·시각 조건. 해당하지 않으면 None."""
    match value:
        case NumberValue(n):
            return _COMPARISONS[operator](key, _big(n))
        case NumberRange(low, high):
            return key.between(_big(low), _big(high))
        case DateBounds():
            return _date_range(key, value)
        case DateTimeBounds():
            return _instant_range(key, value)
    return None


def condition_clause(
    resolved: ResolvedCondition, fields: dict[str, FieldSql], risk: RiskExprs
) -> Expr:
    condition = resolved.condition
    spec = condition.field
    value = resolved.value
    if spec.key == _RISK_KEY and isinstance(value, KeyList | NoValue):
        return _risk(value, condition.operator, risk)
    key = fields[spec.key].key
    found = _discrete_clause(key, spec, condition.operator, value)
    if found is None:
        found = _range_clause(key, condition.operator, value)
    if found is None:
        raise TypeError(f"해석되지 않은 조건 값입니다: {value!r}")
    return found


def where_clause(
    report: ResolvedReport, fields: dict[str, FieldSql], risk: RiskExprs
) -> Expr | None:
    """모든 조건을 `combine`으로 묶은 WHERE. 조건이 없으면 None."""
    definition = report.definition
    combine = and_ if definition.combine is Combine.AND else or_
    split = definition.action_filter() is ActionFilter.EXISTS
    on_rows: list[Expr] = []
    on_actions: list[Expr] = []
    for resolved in report.conditions:
        clause = condition_clause(resolved, fields, risk)
        by_action = split and resolved.condition.field.entity is Entity.ACTION
        (on_actions if by_action else on_rows).append(clause)
    if on_actions:
        on_rows.append(
            exists(
                select(literal_column("1"))
                .select_from(ACTIONS)
                .where(ACTIONS.c.deal_id == DEALS.c.id, combine(*on_actions))
                .correlate(DEALS)
            )
        )
    if not on_rows:
        return None
    return and_(*on_rows) if definition.combine is Combine.AND else or_(*on_rows)
