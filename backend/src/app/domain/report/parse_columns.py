"""원시 컬럼을 검증해 `ReportColumn`으로 만든다. 위반은 모두 모은다."""

from enum import StrEnum
from typing import TYPE_CHECKING

from app.domain.report.catalog import find_field
from app.domain.report.definition import ReportColumn
from app.domain.report.labels import AGGREGATE_LABELS
from app.domain.report.vocabulary import (
    COLUMNS_MAX,
    COLUMNS_MIN,
    LABEL_MAX,
    PREFIX_MAX,
    PREFIX_MIN,
    Aggregate,
    Format,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.report.errors import IssueLog, IssueScope
    from app.domain.report.fields import FieldSpec
    from app.domain.report.raw import RawColumn

_KEY_ECHO_MAX = 50


def enum_member[E: StrEnum](enum: type[E], raw: object) -> E | None:
    """문자열이 enum 값과 정확히 같으면 그 멤버, 아니면 None."""
    if not isinstance(raw, str):
        return None
    try:
        return enum(raw)
    except ValueError:
        return None


def unknown_field_message(key: str) -> str:
    return f"허용되지 않은 필드입니다: {key[:_KEY_ECHO_MAX]}"


def parse_columns(raw: Sequence[RawColumn], log: IssueLog) -> tuple[ReportColumn, ...]:
    if not COLUMNS_MIN <= len(raw) <= COLUMNS_MAX:
        log.add(
            ("columns",),
            "columns-count",
            f"컬럼은 {COLUMNS_MIN}개 이상 {COLUMNS_MAX}개 이하로 지정하세요",
        )
        return ()
    grouped = any(column.group for column in raw)
    parsed = (_parse_column(i, column, grouped, log) for i, column in enumerate(raw))
    return tuple(column for column in parsed if column is not None)


def _parse_column(i: int, raw: RawColumn, grouped: bool, log: IssueLog) -> ReportColumn | None:
    scope = log.scope("columns", i)
    field = find_field(raw.field)
    if field is None:
        scope.add("unknown-field", unknown_field_message(raw.field), "field")
        return None
    label = _label(raw.label, field, scope)
    fmt = _format(raw.format, field, scope)
    prefix_length = _prefix_length(raw.prefix_length, scope)
    aggregate = _aggregate(raw, field, grouped=grouped, scope=scope)
    if scope.failed:
        return None
    return ReportColumn(field, label, fmt, prefix_length, raw.group, aggregate)


def _label(raw: str | None, field: FieldSpec, scope: IssueScope) -> str:
    if raw is None:
        return field.label
    text = raw.strip() if isinstance(raw, str) and "\x00" not in raw else ""
    if not text or len(text) > LABEL_MAX:
        scope.add(
            "label-invalid", f"표시 이름은 공백이 아닌 {LABEL_MAX}자 이하여야 합니다", "label"
        )
    return text


def _format(raw: str | None, field: FieldSpec, scope: IssueScope) -> Format | None:
    if raw is None:
        return field.default_format
    fmt = enum_member(Format, raw)
    if fmt is None or fmt not in field.formats:
        message = (
            "이 필드는 포맷을 고를 수 없습니다"
            if not field.formats
            else "이 필드에 쓸 수 없는 포맷입니다. 가능: "
            + ", ".join(f.value for f in field.formats)
        )
        scope.add("format-not-allowed", message, "format")
        return None
    return fmt


def _prefix_length(raw: object, scope: IssueScope) -> int | None:
    """앞 N자 보기 옵션. 모든 컬럼에서 null 또는 1~200의 정수(bool 제외)."""
    if raw is None:
        return None
    if type(raw) is not int or not PREFIX_MIN <= raw <= PREFIX_MAX:
        scope.add(
            "value-invalid",
            f"앞 N자의 N은 {PREFIX_MIN}~{PREFIX_MAX}의 정수여야 합니다",
            "prefix_length",
        )
        return None
    return raw


def _aggregate(
    raw: RawColumn, field: FieldSpec, *, grouped: bool, scope: IssueScope
) -> Aggregate | None:
    if raw.group:
        if not field.groupable:
            scope.add("group-not-allowed", "이 필드는 그룹핑할 수 없습니다", "group")
        elif raw.aggregate is not None:
            scope.add(
                "aggregate-not-allowed", "그룹 컬럼에는 집계를 지정할 수 없습니다", "aggregate"
            )
        return None
    if not grouped:
        _reject_ungrouped(raw, field, scope)
        return None
    return _grouped_aggregate(raw.aggregate, field, scope)


def _reject_ungrouped(raw: RawColumn, field: FieldSpec, scope: IssueScope) -> None:
    if field.requires_grouping:
        scope.add(
            "grouping-required", "이 컬럼은 그룹핑할 때만 쓸 수 있습니다. 그룹 컬럼을 추가하세요"
        )
    elif raw.aggregate is not None:
        scope.add(
            "aggregate-not-allowed",
            "그룹핑이 없으면 집계를 지정할 수 없습니다. 그룹 컬럼을 추가하거나 집계를 빼세요",
            "aggregate",
        )


def _grouped_aggregate(raw: str | None, field: FieldSpec, scope: IssueScope) -> Aggregate | None:
    allowed = field.allowed_aggregates()
    if raw is None:
        if field.default_aggregate is None:
            names = " 또는 ".join(AGGREGATE_LABELS[a] for a in allowed)
            scope.add(
                "aggregate-required",
                f"그룹핑할 때 이 컬럼은 집계({names})를 골라야 합니다. 그룹핑하거나 빼세요",
                "aggregate",
            )
        return field.default_aggregate
    aggregate = enum_member(Aggregate, raw)
    if aggregate is None or aggregate not in allowed:
        names = " 또는 ".join(AGGREGATE_LABELS[a] for a in allowed)
        scope.add(
            "aggregate-not-allowed",
            f"그룹핑할 때 이 컬럼은 {names}만 고를 수 있습니다. 그룹핑하거나 빼세요",
            "aggregate",
        )
        return None
    return aggregate
