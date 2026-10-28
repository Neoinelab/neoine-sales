"""리포트 한 건의 SQL 조각 공급자: 필드 식, 컬럼 값·그룹 식, WHERE, FROM.

식은 쓸 때 만들어지고 필요한 JOIN이 그때 등록되므로 `source()`는 모든 식을 만든 뒤 마지막에 부른다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.report.definition import RowScope
from app.domain.report.vocabulary import Aggregate, FieldType
from app.infra.db.report_buckets import bucket
from app.infra.db.report_conditions import where_clause
from app.infra.db.report_fields_action import action_fields
from app.infra.db.report_fields_deal import deal_fields
from app.infra.db.report_joins import Joins
from app.infra.db.report_risk import RiskExprs

if TYPE_CHECKING:
    from sqlalchemy import FromClause

    from app.domain.report.definition import ReportColumn
    from app.domain.report.fields import FieldSpec
    from app.domain.report.resolve import ResolvedReport
    from app.infra.db.report_fields import Expr, FieldSql

_DATE_TYPES = frozenset({FieldType.DATE, FieldType.DATETIME})
_COUNTS = frozenset({Aggregate.COUNT, Aggregate.COUNT_DISTINCT})


@dataclass(frozen=True, slots=True)
class GroupExprs:
    """그룹 컬럼의 세 식: 묶는 기준(key), 결과 값(value), 정렬(order). 같은 식이면 같은 객체."""

    key: Expr
    value: Expr
    order: Expr


class ReportParts:
    def __init__(self, report: ResolvedReport) -> None:
        self.report = report
        self.definition = report.definition
        self.context = report.context
        self._joins = Joins()
        self._risk = RiskExprs(report.context)
        self._fields = {
            **deal_fields(self._joins, report.context, self._risk),
            **action_fields(self._joins),
        }

    def is_action_scope(self) -> bool:
        return self.definition.row_scope() is RowScope.ACTION

    def field(self, spec: FieldSpec) -> FieldSql:
        return self._fields[spec.key]

    def value_of(self, column: ReportColumn) -> Expr:
        """그룹핑하지 않는 결과 열의 값 식(포맷 반영)."""
        spec = column.field
        sql = self.field(spec)
        if spec.type in _DATE_TYPES:
            return bucket(sql.key, spec.type, column.format, self.context)
        return sql.value

    def group_exprs(self, column: ReportColumn) -> GroupExprs:
        spec = column.field
        sql = self.field(spec)
        if spec.type in _DATE_TYPES:
            grouped = self.value_of(column)
            return GroupExprs(grouped, grouped, grouped)
        return GroupExprs(sql.key, self.value_of(column), sql.order)

    def measure(self, column: ReportColumn) -> Expr:
        """집계할 원본 식. 건수는 key, 숫자 집계는 값."""
        sql = self.field(column.field)
        if column.aggregate in _COUNTS:
            return sql.key
        return sql.value

    def where(self) -> Expr | None:
        return where_clause(self.report, self._fields, self._risk)

    def source(self) -> FromClause:
        return self._joins.source(with_actions=self.is_action_scope())
