"""상대 기간·날짜를 절대 범위로 풀어 SQL 생성기가 그대로 쓸 수 있게 한다."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from app.domain.common.business_date import start_of_business_day
from app.domain.deal.period import month_range, quarter_of, quarter_range
from app.domain.report.condition_values import (
    ConditionValue,
    DateRange,
    DateValue,
    RelativeValue,
)
from app.domain.report.vocabulary import FieldType, Operator, RelativePeriod

if TYPE_CHECKING:
    from app.domain.deal.risk import RiskBasis
    from app.domain.report.definition import ReportCondition, ReportDefinition

_ONE_DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class ReportContext:
    """조회 시점의 서버 기준: 업무 날짜, SQL 날짜 변환용 UTC 오프셋, 경고 판정 기준."""

    today: date
    utc_offset: timedelta
    risk: RiskBasis


@dataclass(frozen=True, slots=True)
class DateBounds:
    """날짜 필드의 절대 범위. 양끝 포함이고 한쪽이 None이면 그쪽은 열려 있다."""

    first: date | None
    last: date | None


@dataclass(frozen=True, slots=True)
class DateTimeBounds:
    """시각 필드의 절대 범위. 반개구간 [start, end)이고 한쪽이 None이면 그쪽은 열려 있다."""

    start: datetime | None
    end: datetime | None


type ResolvedValue = ConditionValue | DateBounds | DateTimeBounds


@dataclass(frozen=True, slots=True)
class ResolvedCondition:
    condition: ReportCondition
    value: ResolvedValue


@dataclass(frozen=True, slots=True)
class ResolvedReport:
    definition: ReportDefinition
    conditions: tuple[ResolvedCondition, ...]
    context: ReportContext


def _relative_bounds(value: RelativeValue, today: date) -> DateBounds:
    match value.period:
        case RelativePeriod.THIS_YEAR:
            return DateBounds(*quarter_range(today.year, None))
        case RelativePeriod.THIS_QUARTER:
            return DateBounds(*quarter_range(today.year, quarter_of(today)))
        case RelativePeriod.THIS_MONTH:
            return DateBounds(*month_range(today.year, today.month))
        case RelativePeriod.LAST_N_DAYS:
            days = value.days or 1
            return DateBounds(today - timedelta(days=days - 1), today)
        case RelativePeriod.BEFORE_TODAY:
            return DateBounds(None, today - _ONE_DAY)


def _date_bounds(condition: ReportCondition, value: ConditionValue, today: date) -> DateBounds:
    match value:
        case RelativeValue():
            return _relative_bounds(value, today)
        case DateRange(first, last):
            return DateBounds(first, last)
        case DateValue(day) if condition.operator is Operator.BEFORE:
            return DateBounds(None, day - _ONE_DAY)
        case DateValue(day):
            return DateBounds(day + _ONE_DAY, None)
    raise TypeError(f"날짜 조건 값이 아닙니다: {value!r}")


def _as_instants(bounds: DateBounds) -> DateTimeBounds:
    start = start_of_business_day(bounds.first) if bounds.first else None
    end = start_of_business_day(bounds.last + _ONE_DAY) if bounds.last else None
    return DateTimeBounds(start, end)


def _resolve_condition(condition: ReportCondition, today: date) -> ResolvedCondition:
    field_type = condition.field.type
    if field_type not in {FieldType.DATE, FieldType.DATETIME}:
        return ResolvedCondition(condition, condition.value)
    bounds = _date_bounds(condition, condition.value, today)
    if field_type is FieldType.DATE:
        return ResolvedCondition(condition, bounds)
    return ResolvedCondition(condition, _as_instants(bounds))


def resolve_report(definition: ReportDefinition, context: ReportContext) -> ResolvedReport:
    """날짜·시각 조건을 오늘(업무 날짜) 기준의 절대 범위로 풀고, 나머지 값은 그대로 둔다."""
    return ResolvedReport(
        definition,
        tuple(_resolve_condition(c, context.today) for c in definition.conditions),
        context,
    )
