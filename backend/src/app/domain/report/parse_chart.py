"""원시 차트를 정의 기준으로 검증해 `ChartSettings`로 만든다. 위반은 모두 모아 알린다.

규칙은 `KIND_RULES`(종류별 표)에 있고, 여기서는 표를 읽어 판정만 한다.
"""

import math
from typing import TYPE_CHECKING

from app.domain.report.chart import (
    CHART_TEXT_MAX,
    CHART_VALUES_MAX,
    KIND_RULES,
    PERCENT_MAX,
    SAFE_INTEGER_MAX,
    ChartKind,
    ChartSettings,
    KindRule,
    LegendPosition,
)
from app.domain.report.errors import IssueLog, ReportDefinitionError
from app.domain.report.parse_columns import enum_member

if TYPE_CHECKING:
    from app.domain.report.definition import ReportDefinition
    from app.domain.report.raw import RawChart

_GROUPS_MAX = 2


class _Columns:
    """정의의 컬럼 index를 그룹 컬럼·값 컬럼으로 나눈 것."""

    def __init__(self, definition: ReportDefinition) -> None:
        columns = definition.columns
        self.groups = [i for i, c in enumerate(columns) if c.group]
        self.values = {i for i, c in enumerate(columns) if not c.group and c.aggregate is not None}


def _index(raw: object) -> int | None:
    return raw if type(raw) is int else None


def parse_chart(raw: RawChart, definition: ReportDefinition) -> ChartSettings:
    """위반이 있으면 `ReportDefinitionError`(위치는 `("chart", ...)`)."""
    log = IssueLog()
    columns = _Columns(definition)
    settings = _parse(raw, columns, log)
    if log.items or settings is None:
        raise ReportDefinitionError(log.items)
    return settings


def _parse(raw: RawChart, columns: _Columns, log: IssueLog) -> ChartSettings | None:
    if not columns.groups:
        log.add(("chart",), "chart-needs-grouping", "그룹핑한 결과로 차트를 만들 수 있습니다")
        return None
    if len(columns.groups) > _GROUPS_MAX:
        log.add(
            ("chart",),
            "chart-too-many-groups",
            "차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다",
        )
        return None
    kind = _kind(raw.kind, len(columns.groups), log)
    rule = KIND_RULES[kind] if kind is not None else None
    category = _category(raw.category, columns, log)
    series = _series(raw.series, category, rule, columns, log)
    values = _values(raw.values, rule, series is not None, columns, log)
    swap = _flag(
        raw.swap, "swap", "chart-swap-invalid", allowed=rule.allows_swap if rule else None, log=log
    )
    secondary = _flag(
        raw.secondary_axis,
        "secondary_axis",
        "chart-secondary-invalid",
        allowed=rule.allows_secondary if rule else None,
        log=log,
        bad_type_code="chart-flag-invalid",
    )
    labels = _flag(raw.data_labels, "data_labels", "chart-flag-invalid", allowed=None, log=log)
    texts = [_text(getattr(raw, key), key, log) for key in _TEXT_KEYS]
    legend = enum_member(LegendPosition, raw.legend)
    if legend is None:
        log.add(
            ("chart", "legend"),
            "chart-legend-invalid",
            "범례 위치는 top·right·bottom·none 중 하나입니다",
        )
    low, high = _range(raw, rule, log)
    if log.items or kind is None or category is None or legend is None:
        return None
    return ChartSettings(
        kind=kind,
        category=category,
        series=series,
        values=tuple(values),
        swap=bool(swap),
        title=texts[0],
        legend=legend,
        data_labels=bool(labels),
        category_axis_title=texts[1],
        value_axis_title=texts[2],
        value_min=low,
        value_max=high,
        secondary_axis=bool(secondary),
    )


_TEXT_KEYS = ("title", "category_axis_title", "value_axis_title")


def _kind(raw: object, group_count: int, log: IssueLog) -> ChartKind | None:
    kind = enum_member(ChartKind, raw)
    if kind is None:
        log.add(("chart", "kind"), "chart-kind-invalid", "차트 종류를 알 수 없습니다")
    elif group_count > KIND_RULES[kind].max_groups:
        log.add(
            ("chart", "kind"),
            "chart-kind-groups",
            "원·도넛·분산형·콤보 차트는 그룹핑 컬럼이 1개일 때 만들 수 있습니다",
        )
    return kind


def _category(raw: object, columns: _Columns, log: IssueLog) -> int | None:
    index = _index(raw)
    if index is None or index not in columns.groups:
        log.add(
            ("chart", "category"), "chart-category-invalid", "범주 열은 그룹핑한 컬럼이어야 합니다"
        )
        return None
    return index


def _series(
    raw: object, category: int | None, rule: KindRule | None, columns: _Columns, log: IssueLog
) -> int | None:
    location = ("chart", "series")
    if raw is None:
        if rule is not None and rule.allows_series and len(columns.groups) == _GROUPS_MAX:
            log.add(
                location,
                "chart-series-required",
                "그룹핑 컬럼이 2개면 나머지 하나를 계열로 고르세요",
            )
        return None
    index = _index(raw)
    if rule is not None and not rule.allows_series:
        log.add(location, "chart-series-invalid", "이 종류는 계열 열을 쓰지 않습니다")
        return None
    if index is None or index not in columns.groups or index == category:
        log.add(
            location,
            "chart-series-invalid",
            "계열 열은 범주와 다른 그룹핑 컬럼이어야 합니다",
        )
        return None
    return index


def _values(
    raw: object, rule: KindRule | None, has_series: bool, columns: _Columns, log: IssueLog
) -> list[int]:
    if not isinstance(raw, list):
        log.add(("chart", "values"), "chart-values-invalid", "값 열을 고르세요")
        return []
    if len(raw) > CHART_VALUES_MAX:
        log.add(
            ("chart", "values"),
            "chart-values-count",
            f"값 열은 최대 {CHART_VALUES_MAX}개까지 고를 수 있습니다",
        )
        return []
    picked: list[int] = []
    for i, item in enumerate(raw):
        index = _index(item)
        if index is None or index not in columns.values:
            log.add(
                ("chart", "values", i),
                "chart-value-invalid",
                "값 열은 숫자(집계) 컬럼이어야 합니다",
            )
        elif index in picked:
            log.add(
                ("chart", "values", i),
                "chart-value-duplicate",
                "같은 값 열을 두 번 고를 수 없습니다",
            )
        else:
            picked.append(index)
    if rule is not None:
        _check_count(len(raw), rule, has_series=has_series, log=log)
    return picked


def _check_count(count: int, rule: KindRule, *, has_series: bool, log: IssueLog) -> None:
    low, high = rule.value_count_range(has_series=has_series)
    if low <= count <= high:
        return
    wanted = f"{low}개" if low == high else f"{low}~{high}개"
    log.add(("chart", "values"), "chart-values-count", f"이 차트는 값 열을 {wanted} 골라야 합니다")


def _flag(  # noqa: PLR0913
    raw: object,
    key: str,
    code: str,
    *,
    allowed: bool | None,
    log: IssueLog,
    bad_type_code: str | None = None,
) -> bool:
    """bool이어야 하고, `allowed`가 False(알려진 종류가 막음)이면 true일 수 없다."""
    if type(raw) is not bool:
        message = "켜기·끄기 값이어야 합니다"
        if key == "swap":
            message = "이 차트는 행/열 전환을 쓸 수 없습니다"
        log.add(("chart", key), bad_type_code or code, message)
        return False
    if raw and allowed is False:
        message = (
            "보조 축은 콤보 차트에서만 쓸 수 있습니다"
            if key == "secondary_axis"
            else "이 차트는 행/열 전환을 쓸 수 없습니다"
        )
        log.add(("chart", key), code, message)
    return raw


def _text(raw: object, key: str, log: IssueLog) -> str:
    if type(raw) is str and "\x00" not in raw and len(raw.strip()) <= CHART_TEXT_MAX:
        return raw.strip()
    log.add(("chart", key), "chart-text-invalid", "100자 이내 글자로 입력하세요")
    return ""


def _number(raw: object) -> bool:
    if raw is None or type(raw) not in {int, float}:
        return False
    if type(raw) is int:
        return abs(raw) <= SAFE_INTEGER_MAX  # float 변환 전에 판정(OverflowError 방지)
    return math.isfinite(raw) and abs(raw) <= SAFE_INTEGER_MAX  # type: ignore[arg-type]


def _range(
    raw: RawChart, rule: KindRule | None, log: IssueLog
) -> tuple[int | float | None, int | float | None]:
    bounds: dict[str, int | float | None] = {}
    for key, value in (("value_min", raw.value_min), ("value_max", raw.value_max)):
        bounds[key] = _bound(key, value, rule, log)
    low, high = bounds["value_min"], bounds["value_max"]
    if low is not None and high is not None and low >= high and not _has_range_issue(log):
        log.add(("chart", "value_max"), "chart-range-order", "최대는 최소보다 커야 합니다")
    return low, high


def _has_range_issue(log: IssueLog) -> bool:
    return any(i.code == "chart-range-invalid" for i in log.items)


def _bound(key: str, value: object, rule: KindRule | None, log: IssueLog) -> int | float | None:
    if value is None:
        return None
    location = ("chart", key)
    if not _number(value):
        log.add(location, "chart-range-invalid", "숫자를 입력하세요")
        return None
    number: int | float = value  # type: ignore[assignment]
    if rule is not None and not rule.allows_value_range:
        log.add(location, "chart-range-invalid", "이 차트는 축 범위를 쓸 수 없습니다")
    elif rule is not None and rule.percent_axis and not 0 <= number <= PERCENT_MAX:
        log.add(location, "chart-range-invalid", "0~100 사이로 입력하세요")
    return number
