"""검증을 마친 리포트 정의. 행 범위·Action 조건 처리·Deal 숫자 중복 방지 같은 판정을 여기서 한다."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from app.domain.report.vocabulary import (
    Aggregate,
    Combine,
    Entity,
    FieldType,
    Format,
    Operator,
    ResultValueType,
    SortDirection,
)

if TYPE_CHECKING:
    from app.domain.report.condition_values import ConditionValue
    from app.domain.report.fields import FieldSpec

_COUNTS = frozenset({Aggregate.COUNT, Aggregate.COUNT_DISTINCT})
_INTEGER_AGGREGATES = frozenset({Aggregate.SUM, Aggregate.MIN, Aggregate.MAX})
_DEAL_ONCE_AGGREGATES = frozenset({Aggregate.SUM, Aggregate.AVG})
_TEXT_DATE_FORMATS = frozenset({Format.QUARTER, Format.MONTH})


class RowScope(StrEnum):
    """결과 행 1개가 가리키는 단위."""

    DEAL = "deal"
    ACTION = "action"


class ActionFilter(StrEnum):
    """Action 필드가 쓰이는 방식: 없음 / 조건에만(EXISTS) / 컬럼(JOIN)."""

    NONE = "none"
    EXISTS = "exists"
    JOIN = "join"


@dataclass(frozen=True, slots=True)
class ReportColumn:
    field: FieldSpec
    label: str
    format: Format | None
    prefix_length: int | None
    group: bool
    aggregate: Aggregate | None
    sort: SortDirection | None

    def value_type(self) -> ResultValueType:
        """결과 열 값의 JSON 모양(포맷·집계 반영)."""
        if self.aggregate in _COUNTS:
            return ResultValueType.INTEGER
        if self.aggregate is Aggregate.AVG:
            return ResultValueType.DECIMAL
        if self.aggregate in _INTEGER_AGGREGATES or self.field.type is FieldType.NUMBER:
            return ResultValueType.INTEGER
        if self.field.type in {FieldType.DATE, FieldType.DATETIME}:
            return self._date_value_type()
        return ResultValueType.TEXT

    def _date_value_type(self) -> ResultValueType:
        if self.format is Format.YEAR:
            return ResultValueType.INTEGER
        if self.format in _TEXT_DATE_FORMATS:
            return ResultValueType.TEXT
        if self.field.type is FieldType.DATE or self.format is Format.YMD:
            return ResultValueType.DATE
        return ResultValueType.DATETIME

    def uses_deal_number_once(self) -> bool:
        """Deal 숫자의 합계·평균이면, Action 행 범위에서 Deal당 한 번만 센다."""
        return not self.group and self.field.deal_number and self.aggregate in _DEAL_ONCE_AGGREGATES


@dataclass(frozen=True, slots=True)
class ReportCondition:
    field: FieldSpec
    operator: Operator
    value: ConditionValue


@dataclass(frozen=True, slots=True)
class ReportSort:
    column: int
    direction: SortDirection


@dataclass(frozen=True, slots=True)
class ReportDefinition:
    columns: tuple[ReportColumn, ...]
    conditions: tuple[ReportCondition, ...]
    combine: Combine
    row_limit: int

    def sort_keys(self) -> tuple[ReportSort, ...]:
        """정렬을 지정한 컬럼만, 컬럼 순서대로(앞 컬럼이 우선)."""
        return tuple(
            ReportSort(i, column.sort) for i, column in enumerate(self.columns) if column.sort
        )

    def is_grouped(self) -> bool:
        return any(column.group for column in self.columns)

    def row_scope(self) -> RowScope:
        """Action 필드(`action.count` 포함)가 컬럼에 하나라도 있으면 Action 1건이 한 행이다."""
        if any(column.field.entity is Entity.ACTION for column in self.columns):
            return RowScope.ACTION
        return RowScope.DEAL

    def action_filter(self) -> ActionFilter:
        if self.row_scope() is RowScope.ACTION:
            return ActionFilter.JOIN
        if any(condition.field.entity is Entity.ACTION for condition in self.conditions):
            return ActionFilter.EXISTS
        return ActionFilter.NONE

    def deal_numbers_once(self) -> bool:
        """Action 행 범위의 그룹핑에서 Deal 숫자 합계·평균을 그룹마다 Deal당 한 번 계산하는가."""
        return (
            self.row_scope() is RowScope.ACTION
            and self.is_grouped()
            and any(column.uses_deal_number_once() for column in self.columns)
        )
