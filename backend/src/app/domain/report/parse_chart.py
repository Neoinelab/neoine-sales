"""원시 차트를 정의 기준으로 검증해 `ChartSettings`로 만든다. 위반은 모두 모아 알린다.

규칙은 `KIND_RULES`(종류별 표)에 있고, 여기서는 표를 읽어 판정만 한다.
"""

from typing import TYPE_CHECKING

from app.domain.report.chart import ChartSettings, LegendPosition
from app.domain.report.chart_kinds import CHART_VALUES_MAX, KIND_RULES, ChartKind, KindRule
from app.domain.report.errors import IssueLog, ReportDefinitionError
from app.domain.report.parse_chart_fields import check_flag, check_range, check_text
from app.domain.report.parse_chart_options import (
    parse_combo_series,
    parse_histogram,
    parse_show_total,
)
from app.domain.report.parse_columns import enum_member
from app.domain.report.vocabulary import ResultValueType

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
        # 그룹핑 없는 히스토그램의 값 열: 집계 없는 숫자 컬럼
        self.numbers = {
            i
            for i, c in enumerate(columns)
            if not c.group
            and c.aggregate is None
            and c.value_type() in {ResultValueType.INTEGER, ResultValueType.DECIMAL}
        }


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
    if len(columns.groups) > _GROUPS_MAX:
        log.add(
            ("chart",),
            "chart-too-many-groups",
            "차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다",
        )
        return None
    kind = _kind(raw.kind, len(columns.groups), log)
    rule = KIND_RULES[kind] if kind is not None else None
    if not columns.groups and (rule is None or rule.min_groups > 0):
        if rule is not None:
            log.add(
                ("chart",),
                "chart-needs-grouping",
                "그룹핑한 결과로 차트를 만들 수 있습니다(히스토그램 제외)",
            )
        return None
    category = _category(raw.category, rule, columns, log)
    series = _series(raw.series, category, rule, columns, log)
    values = _values(raw.values, rule, series is not None, columns, log)
    swap = check_flag(
        raw.swap, "swap", "chart-swap-invalid", allowed=rule.allows_swap if rule else None, log=log
    )
    secondary = check_flag(
        raw.secondary_axis,
        "secondary_axis",
        "chart-secondary-invalid",
        allowed=rule.allows_secondary if rule else None,
        log=log,
        bad_type_code="chart-flag-invalid",
    )
    labels = check_flag(raw.data_labels, "data_labels", "chart-flag-invalid", allowed=None, log=log)
    texts = [check_text(getattr(raw, key), key, log) for key in _TEXT_KEYS]
    legend = enum_member(LegendPosition, raw.legend)
    if legend is None:
        log.add(
            ("chart", "legend"),
            "chart-legend-invalid",
            "범례 위치는 top·right·bottom·none 중 하나입니다",
        )
    low, high = check_range(raw, rule, log)
    histogram = parse_histogram(raw.histogram, rule, log)
    show_total = parse_show_total(raw.show_total, rule, log)
    count = len(raw.values) if isinstance(raw.values, list) else None
    combo = parse_combo_series(raw.combo_series, rule, count, raw.secondary_axis, log)
    if log.items or kind is None or legend is None:
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
        secondary_axis=any(s.secondary for s in combo) if combo else bool(secondary),
        histogram=histogram,
        show_total=show_total,
        combo_series=combo,
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
            f"이 차트는 그룹핑 컬럼이 {KIND_RULES[kind].max_groups}개 이하일 때 만들 수 있습니다",
        )
    return kind


def _category(raw: object, rule: KindRule | None, columns: _Columns, log: IssueLog) -> int | None:
    if rule is not None and not rule.uses_category:
        if raw is not None:
            log.add(
                ("chart", "category"),
                "chart-category-invalid",
                "이 차트는 범주 열을 쓰지 않습니다",
            )
        return None
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
        if index is None or index not in _value_candidates(rule, columns):
            message = (
                "값 열은 숫자 컬럼이어야 합니다"
                if _ungrouped_histogram(rule, columns)
                else "값 열은 숫자(집계) 컬럼이어야 합니다"
            )
            log.add(("chart", "values", i), "chart-value-invalid", message)
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


def _ungrouped_histogram(rule: KindRule | None, columns: _Columns) -> bool:
    return rule is not None and rule.min_groups == 0 and not columns.groups


def _value_candidates(rule: KindRule | None, columns: _Columns) -> set[int]:
    return columns.numbers if _ungrouped_histogram(rule, columns) else columns.values


def _check_count(count: int, rule: KindRule, *, has_series: bool, log: IssueLog) -> None:
    low, high = rule.value_count_range(has_series=has_series)
    if low <= count <= high:
        return
    wanted = f"{low}개" if low == high else f"{low}~{high}개"
    log.add(("chart", "values"), "chart-values-count", f"이 차트는 값 열을 {wanted} 골라야 합니다")
