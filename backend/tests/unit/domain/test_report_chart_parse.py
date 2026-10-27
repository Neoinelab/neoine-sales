"""차트 설정 검증 `parse_chart` (Reports 4단계 AC1·2·13): 정의 기준으로 판정하고 위반을 모은다.

위치는 `/query`와 같은 규약의 `("chart", ...)`이고, 컬럼은 정의 `columns`의 index로 가리킨다.
종류별 규칙표(계획 4.3)는 종류마다 한 줄씩 이 파일의 경계 테스트가 고정한다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from app.domain.report.chart import ChartKind, ChartSettings, LegendPosition
from app.domain.report.errors import ReportDefinitionError
from app.domain.report.parse import parse_report_definition
from app.domain.report.parse_chart import parse_chart
from tests.support.chart_defs import chart_definition, chart_issues, raw_chart

if TYPE_CHECKING:
    from app.domain.report.raw import RawReportDefinition

ONE = chart_definition(1, 11)  # 0 = 그룹, 1..11 = 집계 값
TWO = chart_definition(2, 11)  # 0·1 = 그룹, 2..12 = 집계 값
ALL_KINDS = [k.value for k in ChartKind]
ONE_GROUP_ONLY = ["pie", "doughnut", "scatter", "combo"]
BAR_LIKE = ["bar", "horizontal_bar", "stacked_bar", "stacked_100_bar", "line", "area"]
TEXT_KEYS = ["title", "category_axis_title", "value_axis_title"]


def _parse(definition: RawReportDefinition, chart: Any) -> ChartSettings:  # noqa: ANN401
    return parse_chart(chart, parse_report_definition(definition))


def _minimal(kind: str) -> Any:  # noqa: ANN401 - RawChart
    """규칙표에 맞는 최소 설정(그룹 1개 정의 ONE 기준)."""
    values = [1, 2] if kind in {"scatter", "combo"} else [1]
    return raw_chart(kind, 0, values)


# ---- AC13: 종류 10개 ----


def test_chart_kind_values_are_the_ten_keys_of_the_plan() -> None:
    assert sorted(ALL_KINDS) == sorted(
        [
            "bar",
            "horizontal_bar",
            "stacked_bar",
            "stacked_100_bar",
            "line",
            "area",
            "pie",
            "doughnut",
            "scatter",
            "combo",
        ]
    )


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_each_chart_kind_is_accepted_with_a_valid_setting(kind: str) -> None:
    settings = _parse(ONE, _minimal(kind))

    assert settings.kind == ChartKind(kind)
    assert settings.category == 0
    assert settings.series is None


def test_minimal_chart_gets_the_documented_defaults() -> None:
    settings = _parse(ONE, raw_chart("bar", 0, [1]))

    assert settings == ChartSettings(
        kind=ChartKind.BAR,
        category=0,
        series=None,
        values=(1,),
        swap=False,
        title="",
        legend=LegendPosition.TOP,
        data_labels=False,
        category_axis_title="",
        value_axis_title="",
        value_min=None,
        value_max=None,
        secondary_axis=False,
    )


def test_every_option_is_kept_when_given() -> None:
    chart = raw_chart(
        "stacked_bar",
        1,
        [2],
        series=0,
        swap=True,
        title="Vendor별",
        legend="right",
        data_labels=True,
        category_axis_title="분기",
        value_axis_title="금액",
        value_min=0,
        value_max=1000.5,
    )

    assert _parse(TWO, chart) == ChartSettings(
        kind=ChartKind.STACKED_BAR,
        category=1,
        series=0,
        values=(2,),
        swap=True,
        title="Vendor별",
        legend=LegendPosition.RIGHT,
        data_labels=True,
        category_axis_title="분기",
        value_axis_title="금액",
        value_min=0,
        value_max=1000.5,
        secondary_axis=False,
    )


# ---- 정의 기준 (규칙 1·2) ----


@pytest.mark.parametrize("kind", [*ALL_KINDS, "nope"])
def test_definition_without_grouping_cannot_have_a_chart(kind: str) -> None:
    found = chart_issues(chart_definition(0), raw_chart(kind, 99, "garbage"))

    assert found == [(("chart",), "chart-needs-grouping")]


def test_three_group_columns_cannot_have_a_chart() -> None:
    found = chart_issues(chart_definition(3, 2), raw_chart("bar", 0, [3]))

    assert found == [(("chart",), "chart-too-many-groups")]


def test_grouping_messages_are_in_korean() -> None:
    with pytest.raises(ReportDefinitionError) as none:
        _parse(chart_definition(0), raw_chart())
    with pytest.raises(ReportDefinitionError) as many:
        _parse(chart_definition(3, 2), raw_chart())

    assert none.value.issues[0].message == "그룹핑한 결과로 차트를 만들 수 있습니다"
    assert many.value.issues[0].message == "차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다"


# ---- 종류 (규칙 3·4) ----


@pytest.mark.parametrize("kind", ["Bar", "column", "", " bar", "bar ", 1, None, True, ["bar"]])
def test_unknown_kind_is_rejected_at_chart_kind(kind: object) -> None:
    found = chart_issues(ONE, raw_chart(kind, 0, [1]))

    assert found == [(("chart", "kind"), "chart-kind-invalid")]


@pytest.mark.parametrize("kind", ONE_GROUP_ONLY)
def test_pie_doughnut_scatter_combo_need_exactly_one_group(kind: str) -> None:
    values = [2, 3] if kind in {"scatter", "combo"} else [2]
    found = chart_issues(TWO, raw_chart(kind, 0, values))

    assert (("chart", "kind"), "chart-kind-groups") in found


@pytest.mark.parametrize("kind", BAR_LIKE)
def test_bar_like_kinds_accept_two_groups_with_a_series(kind: str) -> None:
    settings = _parse(TWO, raw_chart(kind, 0, [2], series=1))

    assert (settings.category, settings.series, settings.values) == (0, 1, (2,))


# ---- 범주 (규칙 5) ----


@pytest.mark.parametrize("category", [-1, 99, 12, "0", 0.0, True, False, None, 1, 2])
def test_category_must_be_a_group_column_index(category: object) -> None:
    # ONE: 0만 그룹 컬럼이다(1은 값 컬럼, 12는 범위 밖, bool은 정수로 보지 않는다).
    found = chart_issues(ONE, raw_chart("bar", category, [1]))

    assert found == [(("chart", "category"), "chart-category-invalid")]


def test_category_may_be_either_group_column_with_two_groups() -> None:
    first = _parse(TWO, raw_chart("bar", 0, [2], series=1))
    second = _parse(TWO, raw_chart("bar", 1, [2], series=0))

    assert (first.category, first.series) == (0, 1)
    assert (second.category, second.series) == (1, 0)


# ---- 계열 (규칙 6·7) ----


def test_two_groups_require_the_other_group_as_series() -> None:
    assert chart_issues(TWO, raw_chart("bar", 0, [2])) == [
        (("chart", "series"), "chart-series-required")
    ]
    assert chart_issues(TWO, raw_chart("bar", 0, [2], series=0)) == [
        (("chart", "series"), "chart-series-invalid")
    ]
    assert _parse(TWO, raw_chart("bar", 0, [2], series=1)).series == 1


@pytest.mark.parametrize("series", [2, 99, -1, "1", True, 1.0])
def test_series_must_be_another_group_column(series: object) -> None:
    found = chart_issues(TWO, raw_chart("bar", 0, [2], series=series))

    assert found == [(("chart", "series"), "chart-series-invalid")]


@pytest.mark.parametrize("kind", ["pie", "doughnut", "scatter", "combo"])
def test_kinds_without_series_reject_a_series_value(kind: str) -> None:
    values = [2, 3] if kind in {"scatter", "combo"} else [2]
    # 그룹이 1개인 정의에서 값 컬럼 index를 계열로 준 경우
    found = chart_issues(ONE, raw_chart(kind, 0, values, series=1))

    assert found == [(("chart", "series"), "chart-series-invalid")]


def test_series_with_one_group_is_rejected_even_for_bar() -> None:
    found = chart_issues(ONE, raw_chart("bar", 0, [1], series=0))

    assert found == [(("chart", "series"), "chart-series-invalid")]


# ---- 값 (규칙 8~11) ----


@pytest.mark.parametrize("values", ["1", None, 1, {"0": 1}])
def test_values_must_be_a_list(values: object) -> None:
    found = chart_issues(ONE, raw_chart("bar", 0, values))

    assert found == [(("chart", "values"), "chart-values-invalid")]


def test_value_items_must_be_aggregate_columns() -> None:
    assert chart_issues(ONE, raw_chart("bar", 0, [0])) == [
        (("chart", "values", 0), "chart-value-invalid")
    ]
    assert chart_issues(ONE, raw_chart("bar", 0, [1, 99])) == [
        (("chart", "values", 1), "chart-value-invalid")
    ]
    assert chart_issues(ONE, raw_chart("bar", 0, [True])) == [
        (("chart", "values", 0), "chart-value-invalid")
    ]
    assert chart_issues(ONE, raw_chart("bar", 0, [1, "2"])) == [
        (("chart", "values", 1), "chart-value-invalid")
    ]
    assert chart_issues(ONE, raw_chart("bar", 0, [-1])) == [
        (("chart", "values", 0), "chart-value-invalid")
    ]


def test_group_column_cannot_be_a_value_with_two_groups() -> None:
    found = chart_issues(TWO, raw_chart("bar", 0, [1], series=1))

    assert found == [(("chart", "values", 0), "chart-value-invalid")]


def test_values_must_be_distinct() -> None:
    found = chart_issues(ONE, raw_chart("bar", 0, [1, 2, 1]))

    assert found == [(("chart", "values", 2), "chart-value-duplicate")]


def test_value_count_follows_the_kind_rule() -> None:
    def count_issue(
        definition: RawReportDefinition, kind: str, values: list[int], series: int | None = None
    ) -> bool:
        found = chart_issues(definition, raw_chart(kind, 0, values, series=series))
        return (("chart", "values"), "chart-values-count") in found

    assert count_issue(ONE, "pie", [1, 2])
    assert count_issue(ONE, "doughnut", [1, 2])
    assert count_issue(ONE, "scatter", [1])
    assert count_issue(ONE, "scatter", [1, 2, 3])
    assert count_issue(ONE, "combo", [1])
    assert count_issue(ONE, "combo", list(range(1, 12)))
    assert count_issue(ONE, "bar", list(range(1, 12)))
    assert count_issue(TWO, "bar", [2, 3], series=1)  # 계열이 있으면 값은 정확히 1개


def test_value_count_boundaries_are_accepted() -> None:
    assert len(_parse(ONE, raw_chart("combo", 0, [1, 2])).values) == 2
    assert len(_parse(ONE, raw_chart("combo", 0, list(range(1, 11)))).values) == 10
    assert len(_parse(ONE, raw_chart("bar", 0, list(range(1, 11)))).values) == 10
    assert len(_parse(ONE, raw_chart("scatter", 0, [3, 1])).values) == 2


def test_eleven_values_are_a_single_count_violation() -> None:
    found = chart_issues(ONE, raw_chart("bar", 0, list(range(1, 12))))

    assert found == [(("chart", "values"), "chart-values-count")]


@pytest.mark.parametrize("size", [12, 1000, 100_000])
def test_a_huge_value_list_records_one_violation_not_one_per_item(size: int) -> None:
    # 0은 그룹 컬럼이라 항목마다 값 열이 아니다: 항목별 위반이 쌓이면 응답이 커진다
    found = chart_issues(ONE, raw_chart("bar", 0, [0] * size))

    assert found == [(("chart", "values"), "chart-values-count")]


def test_an_empty_value_list_is_a_count_violation() -> None:
    found = chart_issues(ONE, raw_chart("bar", 0, []))

    assert found == [(("chart", "values"), "chart-values-count")]


def test_value_order_is_kept() -> None:
    assert _parse(ONE, raw_chart("combo", 0, [3, 1, 2])).values == (3, 1, 2)


# ---- 행/열 전환·보조 축 (규칙 12·16) ----


@pytest.mark.parametrize("kind", ["pie", "doughnut", "scatter", "combo"])
def test_swap_is_rejected_where_not_allowed(kind: str) -> None:
    values = [1, 2] if kind in {"scatter", "combo"} else [1]
    found = chart_issues(ONE, raw_chart(kind, 0, values, swap=True))

    assert found == [(("chart", "swap"), "chart-swap-invalid")]


@pytest.mark.parametrize("kind", BAR_LIKE)
def test_swap_is_accepted_for_bar_like_kinds(kind: str) -> None:
    assert _parse(ONE, raw_chart(kind, 0, [1], swap=True)).swap is True


@pytest.mark.parametrize("swap", ["true", 1, 0, None])
def test_swap_must_be_a_boolean(swap: object) -> None:
    found = chart_issues(ONE, raw_chart("bar", 0, [1], swap=swap))

    assert found == [(("chart", "swap"), "chart-swap-invalid")]


@pytest.mark.parametrize("kind", [k for k in ALL_KINDS if k != "combo"])
def test_secondary_axis_is_rejected_outside_combo(kind: str) -> None:
    found = chart_issues(ONE, _with(_minimal(kind), secondary_axis=True))

    assert found == [(("chart", "secondary_axis"), "chart-secondary-invalid")]


def test_secondary_axis_is_accepted_for_combo() -> None:
    assert _parse(ONE, raw_chart("combo", 0, [1, 2], secondary_axis=True)).secondary_axis is True


@pytest.mark.parametrize("flag", ["yes", 1, 0, None])
@pytest.mark.parametrize("key", ["data_labels", "secondary_axis"])
def test_flags_must_be_booleans(key: str, flag: object) -> None:
    found = chart_issues(ONE, raw_chart("bar", 0, [1], **{key: flag}))

    assert found == [(("chart", key), "chart-flag-invalid")]


def _with(chart: Any, **changes: Any) -> Any:  # noqa: ANN401 - RawChart
    import dataclasses  # noqa: PLC0415

    return dataclasses.replace(chart, **changes)


# ---- 글자 (규칙 13) ----


@pytest.mark.parametrize("key", TEXT_KEYS)
def test_texts_are_trimmed(key: str) -> None:
    settings = _parse(ONE, raw_chart("bar", 0, [1], **{key: "  제목 \n"}))

    assert getattr(settings, key) == "제목"


@pytest.mark.parametrize("key", TEXT_KEYS)
def test_text_of_one_hundred_characters_is_accepted(key: str) -> None:
    settings = _parse(ONE, raw_chart("bar", 0, [1], **{key: "가" * 100}))

    assert getattr(settings, key) == "가" * 100


@pytest.mark.parametrize("key", TEXT_KEYS)
def test_spaces_around_a_hundred_characters_do_not_count(key: str) -> None:
    settings = _parse(ONE, raw_chart("bar", 0, [1], **{key: f"  {'a' * 100}  "}))

    assert getattr(settings, key) == "a" * 100


@pytest.mark.parametrize("key", TEXT_KEYS)
@pytest.mark.parametrize("text", ["가" * 101, "a\x00b", 1, None, ["x"]])
def test_invalid_texts_are_rejected_at_their_key(key: str, text: object) -> None:
    found = chart_issues(ONE, raw_chart("bar", 0, [1], **{key: text}))

    assert found == [(("chart", key), "chart-text-invalid")]


def test_blank_text_becomes_empty() -> None:
    assert _parse(ONE, raw_chart("bar", 0, [1], title="   ")).title == ""


# ---- 범례 (규칙 14) ----


@pytest.mark.parametrize("legend", ["top", "right", "bottom", "none"])
def test_legend_accepts_four_positions(legend: str) -> None:
    assert _parse(ONE, raw_chart("bar", 0, [1], legend=legend)).legend == LegendPosition(legend)


@pytest.mark.parametrize("legend", ["left", "TOP", " top", "", None, 1, True])
def test_legend_rejects_anything_else(legend: object) -> None:
    found = chart_issues(ONE, raw_chart("bar", 0, [1], legend=legend))

    assert found == [(("chart", "legend"), "chart-legend-invalid")]


# ---- 값 축 범위 (규칙 17~19) ----


@pytest.mark.parametrize("key", ["value_min", "value_max"])
@pytest.mark.parametrize("number", [True, False, "10", float("inf"), float("-inf"), float("nan")])
def test_range_rejects_non_numbers_and_non_finite(key: str, number: object) -> None:
    found = chart_issues(ONE, raw_chart("bar", 0, [1], **{key: number}))

    assert found == [(("chart", key), "chart-range-invalid")]


@pytest.mark.parametrize("key", ["value_min", "value_max"])
@pytest.mark.parametrize("number", [2**53, -(2**53), 10**30])
def test_range_rejects_numbers_beyond_the_safe_integer(key: str, number: int) -> None:
    found = chart_issues(ONE, raw_chart("bar", 0, [1], **{key: number}))

    assert found == [(("chart", key), "chart-range-invalid")]


@pytest.mark.parametrize("key", ["value_min", "value_max"])
@pytest.mark.parametrize("number", [10**400, -(10**400), 10**309, -(10**309)])
def test_range_rejects_integers_too_large_for_a_float_without_raising(
    key: str, number: int
) -> None:
    found = chart_issues(ONE, raw_chart("bar", 0, [1], **{key: number}))

    assert found == [(("chart", key), "chart-range-invalid")]


def test_range_accepts_integers_floats_and_the_safe_limits() -> None:
    limit = 2**53 - 1

    settings = _parse(ONE, raw_chart("bar", 0, [1], value_min=-limit, value_max=limit))
    decimal = _parse(ONE, raw_chart("bar", 0, [1], value_min=-1.5, value_max=0.25))

    assert (settings.value_min, settings.value_max) == (-limit, limit)
    assert (decimal.value_min, decimal.value_max) == (-1.5, 0.25)


def test_range_with_only_one_side_is_accepted() -> None:
    assert _parse(ONE, raw_chart("bar", 0, [1], value_min=0)).value_max is None
    assert _parse(ONE, raw_chart("bar", 0, [1], value_max=0)).value_min is None


@pytest.mark.parametrize(("low", "high"), [(5, 5), (6, 5), (0.5, 0.5), (1, 0.5)])
def test_range_min_must_be_below_max(low: float, high: float) -> None:
    found = chart_issues(ONE, raw_chart("bar", 0, [1], value_min=low, value_max=high))

    assert found == [(("chart", "value_max"), "chart-range-order")]


@pytest.mark.parametrize("kind", ["pie", "doughnut"])
@pytest.mark.parametrize("key", ["value_min", "value_max"])
def test_range_is_rejected_where_the_kind_has_no_value_axis(kind: str, key: str) -> None:
    found = chart_issues(ONE, raw_chart(kind, 0, [1], **{key: 10}))

    assert found == [(("chart", key), "chart-range-invalid")]


@pytest.mark.parametrize("kind", ["scatter", "combo"])
def test_range_is_accepted_for_scatter_and_combo(kind: str) -> None:
    settings = _parse(ONE, raw_chart(kind, 0, [1, 2], value_min=0, value_max=10))

    assert (settings.value_min, settings.value_max) == (0, 10)


@pytest.mark.parametrize(
    ("key", "number"),
    [("value_min", -1), ("value_min", 101), ("value_max", -1), ("value_max", 101)],
)
def test_percent_stack_range_must_stay_between_zero_and_hundred(key: str, number: int) -> None:
    found = chart_issues(ONE, raw_chart("stacked_100_bar", 0, [1], **{key: number}))

    assert found == [(("chart", key), "chart-range-invalid")]


def test_percent_stack_range_accepts_zero_to_hundred() -> None:
    settings = _parse(ONE, raw_chart("stacked_100_bar", 0, [1], value_min=0, value_max=100))
    inner = _parse(ONE, raw_chart("stacked_100_bar", 0, [1], value_min=10.5, value_max=99.5))

    assert (settings.value_min, settings.value_max) == (0, 100)
    assert (inner.value_min, inner.value_max) == (10.5, 99.5)


# ---- 모아서 보고 / 건너뛰기 (AC2) ----


def test_all_chart_issues_are_reported_together() -> None:
    chart = raw_chart("bar", 1, [0], legend="left")  # 범주·값·범례가 함께 틀림

    with pytest.raises(ReportDefinitionError) as caught:
        _parse(ONE, chart)

    issues = caught.value.issues
    assert {(tuple(i.location), i.code) for i in issues} == {
        (("chart", "category"), "chart-category-invalid"),
        (("chart", "values", 0), "chart-value-invalid"),
        (("chart", "legend"), "chart-legend-invalid"),
    }
    assert len(issues) == 3
    assert str(caught.value) == issues[0].message


def test_every_issue_has_a_korean_message() -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        _parse(ONE, raw_chart("bar", 1, [0], legend="left", title="가" * 101))

    assert all(i.message and i.message.isascii() is False for i in caught.value.issues)


def test_kind_dependent_checks_are_skipped_for_an_unknown_kind() -> None:
    chart = raw_chart(
        "nope", 0, [1, 2, 3, 4, 5], swap=True, secondary_axis=True, value_min=0, value_max=10
    )

    assert chart_issues(ONE, chart) == [(("chart", "kind"), "chart-kind-invalid")]


def test_series_rules_are_skipped_for_an_unknown_kind() -> None:
    found = chart_issues(TWO, raw_chart("nope", 0, [2]))  # 그룹 2개인데 계열이 없지만

    assert found == [(("chart", "kind"), "chart-kind-invalid")]


def test_kind_independent_checks_still_run_for_an_unknown_kind() -> None:
    found = chart_issues(ONE, raw_chart("nope", 5, [0], legend="left"))

    assert {code for _, code in found} == {
        "chart-kind-invalid",
        "chart-category-invalid",
        "chart-value-invalid",
        "chart-legend-invalid",
    }


# ---- 정규화 (AC1) ----


def test_to_raw_is_normalized_and_parses_to_the_same_settings() -> None:
    chart = raw_chart(
        "stacked_bar",
        1,
        [2],
        series=0,
        swap=True,
        title="  Vendor별  ",
        legend="bottom",
        data_labels=True,
        category_axis_title=" 분기",
        value_axis_title="금액 ",
        value_min=0,
        value_max=2.5,
    )
    settings = _parse(TWO, chart)

    normalized = settings.to_raw()

    assert normalized.title == "Vendor별"
    assert (normalized.category_axis_title, normalized.value_axis_title) == ("분기", "금액")
    assert normalized.kind == "stacked_bar"
    assert normalized.legend == "bottom"
    assert normalized.values == [2]
    assert _parse(TWO, normalized) == settings


def test_to_raw_fills_omitted_keys_with_defaults() -> None:
    normalized = _parse(ONE, raw_chart("line", 0, [1])).to_raw()

    assert normalized == raw_chart(
        "line",
        0,
        [1],
        series=None,
        swap=False,
        title="",
        legend="top",
        data_labels=False,
        category_axis_title="",
        value_axis_title="",
        value_min=None,
        value_max=None,
        secondary_axis=False,
    )
