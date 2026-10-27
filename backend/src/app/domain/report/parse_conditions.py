"""원시 조건을 검증해 `ReportCondition`으로 만든다. 위반은 모두 모은다."""

from typing import TYPE_CHECKING

from app.domain.report.catalog import find_field
from app.domain.report.condition_values import (
    ConditionValue,
    ConditionValueError,
    KeyList,
    parse_condition_value,
)
from app.domain.report.definition import ReportCondition
from app.domain.report.parse_columns import enum_member, unknown_field_message
from app.domain.report.vocabulary import CONDITIONS_MAX, FieldType, Operator

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.report.errors import IssueLog
    from app.domain.report.fields import FieldSpec
    from app.domain.report.raw import RawCondition


def parse_conditions(raw: Sequence[RawCondition], log: IssueLog) -> tuple[ReportCondition, ...]:
    if len(raw) > CONDITIONS_MAX:
        log.add(
            ("conditions",), "conditions-count", f"조건은 {CONDITIONS_MAX}개까지 지정할 수 있습니다"
        )
        return ()
    parsed = (_parse_condition(i, condition, log) for i, condition in enumerate(raw))
    return tuple(condition for condition in parsed if condition is not None)


def _parse_condition(i: int, raw: RawCondition, log: IssueLog) -> ReportCondition | None:
    scope = log.scope("conditions", i)
    field = find_field(raw.field)
    if field is None:
        scope.add("unknown-field", unknown_field_message(raw.field), "field")
        return None
    if not field.filterable:
        scope.add("not-filterable", "이 필드는 조건에 쓸 수 없습니다", "field")
        return None
    operator = enum_member(Operator, raw.operator)
    if operator is None or operator not in field.operators:
        names = ", ".join(o.value for o in field.operators)
        scope.add(
            "operator-not-allowed", f"이 필드에 쓸 수 없는 연산자입니다. 가능: {names}", "operator"
        )
        return None
    try:
        value = parse_condition_value(
            operator,
            raw.value,
            is_date=field.type in {FieldType.DATE, FieldType.DATETIME},
            kind=field.value_kind,
        )
    except ConditionValueError as error:
        scope.add("value-invalid", str(error), "value")
        return None
    if not _within_options(field, value):
        names = ", ".join(o.value for o in field.options or ())
        scope.add("value-invalid", f"선택지에 없는 값입니다. 가능: {names}", "value")
        return None
    return ReportCondition(field, operator, value)


def _within_options(field: FieldSpec, value: ConditionValue) -> bool:
    """정적 선택지가 있는 코드 필드는 key가 선택지 안에 있어야 한다(DB 출처 key 제외)."""
    if field.options is None or not isinstance(value, KeyList):
        return True
    return set(value.keys) <= {option.value for option in field.options}
