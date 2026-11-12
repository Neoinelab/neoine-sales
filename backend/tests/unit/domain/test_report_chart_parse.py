"""차트 설정 검증 `parse_chart`: 정의 기준으로 판정하고 위반을 모은다(RC-R3~RC-R17).

기존 10종의 규칙을 고정한다(새 23종은 `test_report_chart_parse_kinds.py`).
위치는 `/query`와 같은 규약의 `("chart", ...)`이고, 컬럼은 정의 `columns`의 index로 가리킨다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from app.domain.report.chart import ChartSettings, LegendPosition
from app.domain.report.chart_kinds import ChartKind
from app.domain.report.errors import ReportDefinitionError
from app.domain.report.parse import parse_report_definition
from app.domain.report.parse_chart import parse_chart
from tests.support.chart_defs import chart_definition, chart_issues, raw_chart

if TYPE_CHECKING:
    from app.domain.report.raw import RawReportDefinition

ONE = chart_definition(1, 11)  # 0 = 그룹, 1..11 = 집계 값
TWO = chart_definition(2, 11)  # 0·1 = 그룹, 2..12 = 집계 값
LEGACY_KINDS = [
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
ALL_KINDS = LEGACY_KINDS  # 새 23종은 test_report_chart_parse_kinds.py
ONE_GROUP_ONLY = ["pie", "doughnut", "scatter", "combo"]
BAR_LIKE = ["bar", "horizontal_bar", "stacked_bar", "stacked_100_bar", "line", "area"]
TEXT_KEYS = ["title", "category_axis_title", "value_axis_title"]


def _parse(definition: RawReportDefinition, chart: Any) -> ChartSettings:  # noqa: ANN401
    return parse_chart(chart, parse_report_definition(definition))


def _minimal(kind: str) -> Any:  # noqa: ANN401 - RawChart
    """규칙표에 맞는 최소 설정(그룹 1개 정의 ONE 기준)."""
    values = [1, 2] if kind in {"scatter", "combo"} else [1]
    return raw_chart(kind, 0, values)


def test_chart_kind_enum_contains_every_legacy_kind_key() -> None:
    """옛 10개 종류 키가 모두 종류 enum에 있다.

    테스트 코드: RC-001
    """
    # when: 이 파일의 기준 종류 목록과 종류 enum의 값을 모은다
    enum_values = {k.value for k in ChartKind}
    # then: enum이 옛 10개 키를 모두 포함한다
    assert set(ALL_KINDS) <= enum_values


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_each_chart_kind_is_accepted_with_a_valid_setting(kind: str) -> None:
    """규칙에 맞는 최소 설정이면 옛 10개 종류를 모두 받아들인다."""
    # when: 종류별 최소 설정을 검증한다
    settings = _parse(ONE, _minimal(kind))

    # then: 종류·범주·계열이 그대로 정규화된다
    assert settings.kind == ChartKind(kind)
    assert settings.category == 0
    assert settings.series is None


def test_minimal_chart_gets_the_documented_defaults() -> None:
    """생략한 키는 명세의 기본값으로 채워진다.

    테스트 코드: RC-029
    """
    # when: 필수 키만 가진 막대 차트를 검증한다
    settings = _parse(ONE, raw_chart("bar", 0, [1]))

    # then: 선택 키가 기본값(범례 위, 끔, 빈 글자, 범위 없음)이다
    assert (settings.kind, settings.category, settings.series, settings.values) == (
        ChartKind.BAR,
        0,
        None,
        (1,),
    )
    assert (settings.swap, settings.title, settings.legend, settings.data_labels) == (
        False,
        "",
        LegendPosition.TOP,
        False,
    )
    assert (settings.category_axis_title, settings.value_axis_title) == ("", "")
    assert (settings.value_min, settings.value_max, settings.secondary_axis) == (None, None, False)


def test_every_option_is_kept_when_given() -> None:
    """준 옵션은 그대로 보관된다."""
    # when: 모든 옵션을 채운 누적 막대 차트를 검증한다
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

    settings = _parse(TWO, chart)

    # then: 범주·계열·값과 모든 선택 옵션이 입력 그대로다
    assert (settings.kind, settings.category, settings.series, settings.values) == (
        ChartKind.STACKED_BAR,
        1,
        0,
        (2,),
    )
    assert (settings.swap, settings.title, settings.legend, settings.data_labels) == (
        True,
        "Vendor별",
        LegendPosition.RIGHT,
        True,
    )
    assert (settings.category_axis_title, settings.value_axis_title) == ("분기", "금액")
    assert (settings.value_min, settings.value_max, settings.secondary_axis) == (0, 1000.5, False)


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_definition_without_grouping_cannot_have_a_chart(kind: str) -> None:
    """그룹핑 없는 정의의 차트는 종류와 상관없이 chart-needs-grouping 하나뿐이다.

    테스트 코드: RC-003
    """
    # when: 종류별로 엉뚱한 설정의 차트를 검증한다 (전제: 그룹핑 없는 정의)
    found = chart_issues(chart_definition(0), raw_chart(kind, 99, "garbage"))

    # then: 위반은 `["chart"]` chart-needs-grouping 하나뿐이다
    assert found == [(("chart",), "chart-needs-grouping")]


def test_ungrouped_definition_with_unknown_kind_reports_only_the_kind() -> None:
    """그룹핑 없는 정의에 모르는 종류를 주면 종류 위반 하나뿐이다.

    테스트 코드: RC-003, RC-005
    """
    # when: 모르는 종류의 차트를 검증한다 (전제: 그룹핑 없는 정의)
    found = chart_issues(chart_definition(0), raw_chart("nope", 99, "garbage"))

    # then: chart-needs-grouping 없이 chart.kind 위반 하나뿐이다
    assert found == [(("chart", "kind"), "chart-kind-invalid")]


def test_three_group_columns_cannot_have_a_chart() -> None:
    """그룹 컬럼이 3개면 chart-too-many-groups 하나뿐이다.

    테스트 코드: RC-004
    """
    # when: 막대 차트를 검증한다 (전제: 그룹 컬럼이 3개인 정의)
    found = chart_issues(chart_definition(3, 2), raw_chart("bar", 0, [3]))

    # then: 위반은 `["chart"]` chart-too-many-groups 하나뿐이다
    assert found == [(("chart",), "chart-too-many-groups")]


def test_grouping_messages_are_in_korean() -> None:
    """그룹핑 위반 문구는 한국어 명세 문구다.

    테스트 코드: RC-003, RC-004
    """
    # when: 그룹 0개 정의와 그룹 3개 정의로 각각 차트를 검증한다
    with pytest.raises(ReportDefinitionError) as none:
        _parse(chart_definition(0), raw_chart())
    with pytest.raises(ReportDefinitionError) as many:
        _parse(chart_definition(3, 2), raw_chart())

    # then: 그룹 없음은 "(히스토그램 제외)" 문구, 3개 이상은 1~2개 문구다
    assert (
        none.value.issues[0].message == "그룹핑한 결과로 차트를 만들 수 있습니다(히스토그램 제외)"
    )
    assert many.value.issues[0].message == "차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다"


@pytest.mark.parametrize("kind", ["Bar", "column", "", " bar", "bar ", 1, None, True, ["bar"]])
def test_unknown_kind_is_rejected_at_chart_kind(kind: object) -> None:
    """모르는 종류 값은 chart.kind 위반이다.

    테스트 코드: RC-005
    """
    # when: 알 수 없는 종류(대소문자·공백·숫자·null 등)로 검증한다
    found = chart_issues(ONE, raw_chart(kind, 0, [1]))

    # then: 위반은 `["chart","kind"]` chart-kind-invalid 하나뿐이다
    assert found == [(("chart", "kind"), "chart-kind-invalid")]


@pytest.mark.parametrize("kind", ONE_GROUP_ONLY)
def test_pie_doughnut_scatter_combo_need_exactly_one_group(kind: str) -> None:
    """원형·도넛형·분산형·콤보는 그룹이 2개면 chart-kind-groups다.

    테스트 코드: RC-006
    """
    # given: 종류에 맞는 값 목록(분산형·콤보는 2개)
    values = [2, 3] if kind in {"scatter", "combo"} else [2]
    # when: 그룹이 2개인 정의에서 그룹 하나만 허용하는 종류를 검증한다
    found = chart_issues(TWO, raw_chart(kind, 0, values))

    # then: `["chart","kind"]` chart-kind-groups 위반이 있다
    assert (("chart", "kind"), "chart-kind-groups") in found


@pytest.mark.parametrize("kind", BAR_LIKE)
def test_bar_like_kinds_accept_two_groups_with_a_series(kind: str) -> None:
    """막대형·꺾은선·영역은 그룹 2개와 계열을 받아들인다.

    테스트 코드: RC-009
    """
    # when: 계열을 지정한 차트를 검증한다 (전제: 그룹 컬럼이 2개인 정의)
    settings = _parse(TWO, raw_chart(kind, 0, [2], series=1))

    # then: 범주·계열·값이 그대로다
    assert (settings.category, settings.series, settings.values) == (0, 1, (2,))


@pytest.mark.parametrize("category", [-1, 99, 12, "0", 0.0, True, False, None, 1, 2])
def test_category_must_be_a_group_column_index(category: object) -> None:
    """범주는 그룹 컬럼 index여야 한다.

    테스트 코드: RC-007
    """
    # when: 그룹이 아닌 컬럼·범위 밖·문자열·bool·null을 범주로 검증한다 (전제: 그룹 컬럼이 0번뿐인
    #   정의)
    # ONE: 0만 그룹 컬럼이다(1은 값 컬럼, 12는 범위 밖, bool은 정수로 보지 않는다).
    found = chart_issues(ONE, raw_chart("bar", category, [1]))

    # then: `["chart","category"]` chart-category-invalid 하나뿐이다
    assert found == [(("chart", "category"), "chart-category-invalid")]


def test_category_may_be_either_group_column_with_two_groups() -> None:
    """그룹이 2개면 범주는 어느 쪽이든 된다.

    테스트 코드: RC-007
    """
    # when: 0번 그룹과 1번 그룹을 각각 범주로 검증한다 (전제: 그룹 컬럼이 2개인 정의)
    first = _parse(TWO, raw_chart("bar", 0, [2], series=1))
    second = _parse(TWO, raw_chart("bar", 1, [2], series=0))

    # then: 각각 나머지 그룹이 계열이다
    assert (first.category, first.series) == (0, 1)
    assert (second.category, second.series) == (1, 0)


def test_two_groups_require_the_other_group_as_series() -> None:
    """그룹이 2개면 나머지 그룹을 계열로 골라야 한다.

    테스트 코드: RC-009, RC-010
    """
    # when: 계열 없음·범주와 같은 계열·올바른 계열로 각각 검증한다 (전제: 그룹 컬럼이 2개인 정의)
    missing = chart_issues(TWO, raw_chart("bar", 0, [2]))
    same_as_category = chart_issues(TWO, raw_chart("bar", 0, [2], series=0))
    valid = _parse(TWO, raw_chart("bar", 0, [2], series=1))

    # then: 계열 없음은 chart-series-required, 범주와 같으면 chart-series-invalid, 올바르면 통과한다
    assert missing == [(("chart", "series"), "chart-series-required")]
    assert same_as_category == [(("chart", "series"), "chart-series-invalid")]
    assert valid.series == 1


@pytest.mark.parametrize("series", [2, 99, -1, "1", True, 1.0])
def test_series_must_be_another_group_column(series: object) -> None:
    """계열은 범주와 다른 그룹 컬럼이어야 한다.

    테스트 코드: RC-010
    """
    # when: 값 컬럼·범위 밖·문자열·bool을 계열로 검증한다 (전제: 그룹 컬럼이 2개인 정의)
    found = chart_issues(TWO, raw_chart("bar", 0, [2], series=series))

    # then: `["chart","series"]` chart-series-invalid 하나뿐이다
    assert found == [(("chart", "series"), "chart-series-invalid")]


@pytest.mark.parametrize("kind", ["pie", "doughnut", "scatter", "combo"])
def test_kinds_without_series_reject_a_series_value(kind: str) -> None:
    """계열을 쓰지 않는 종류에 계열 값을 주면 chart-series-invalid다.

    테스트 코드: RC-010
    """
    # given: 계열을 쓰지 않는 종류에 맞는 값 목록
    values = [2, 3] if kind in {"scatter", "combo"} else [2]
    # when: 그룹 1개 정의에서 값 컬럼 index를 계열로 주고 검증한다
    # 그룹이 1개인 정의에서 값 컬럼 index를 계열로 준 경우
    found = chart_issues(ONE, raw_chart(kind, 0, values, series=1))

    # then: `["chart","series"]` chart-series-invalid 하나뿐이다
    assert found == [(("chart", "series"), "chart-series-invalid")]


def test_series_with_one_group_is_rejected_even_for_bar() -> None:
    """그룹이 1개인 정의에서는 막대도 계열을 받지 않는다.

    테스트 코드: RC-010
    """
    # when: 계열을 준 막대 차트를 검증한다 (전제: 그룹 컬럼이 1개인 정의)
    found = chart_issues(ONE, raw_chart("bar", 0, [1], series=0))

    # then: chart-series-invalid 하나뿐이다
    assert found == [(("chart", "series"), "chart-series-invalid")]


@pytest.mark.parametrize("values", ["1", None, 1, {"0": 1}])
def test_values_must_be_a_list(values: object) -> None:
    """값은 목록이어야 한다.

    테스트 코드: RC-011
    """
    # when: 목록이 아닌 값(문자열·null·숫자·객체)으로 검증한다
    found = chart_issues(ONE, raw_chart("bar", 0, values))

    # then: `["chart","values"]` chart-values-invalid 하나뿐이다
    assert found == [(("chart", "values"), "chart-values-invalid")]


def test_value_items_must_be_aggregate_columns() -> None:
    """값 항목은 집계 컬럼 index여야 하고 위반은 항목 위치에 붙는다.

    테스트 코드: RC-011
    """
    # when: 그룹 컬럼·범위 밖·bool·문자열·음수 항목을 각각 값으로 검증한다
    group = chart_issues(ONE, raw_chart("bar", 0, [0]))
    out_of_range = chart_issues(ONE, raw_chart("bar", 0, [1, 99]))
    boolean = chart_issues(ONE, raw_chart("bar", 0, [True]))
    text = chart_issues(ONE, raw_chart("bar", 0, [1, "2"]))
    negative = chart_issues(ONE, raw_chart("bar", 0, [-1]))

    # then: 각 항목 위치(`["chart","values",i]`)에 chart-value-invalid가 붙는다
    assert group == [(("chart", "values", 0), "chart-value-invalid")]
    assert out_of_range == [(("chart", "values", 1), "chart-value-invalid")]
    assert boolean == [(("chart", "values", 0), "chart-value-invalid")]
    assert text == [(("chart", "values", 1), "chart-value-invalid")]
    assert negative == [(("chart", "values", 0), "chart-value-invalid")]


def test_group_column_cannot_be_a_value_with_two_groups() -> None:
    """그룹이 2개일 때도 그룹 컬럼은 값이 될 수 없다.

    테스트 코드: RC-011
    """
    # when: 그룹 컬럼을 값으로 준 차트를 검증한다 (전제: 그룹 컬럼이 2개인 정의)
    found = chart_issues(TWO, raw_chart("bar", 0, [1], series=1))

    # then: `["chart","values",0]` chart-value-invalid 하나뿐이다
    assert found == [(("chart", "values", 0), "chart-value-invalid")]


def test_values_must_be_distinct() -> None:
    """같은 값 열을 두 번 고르면 두 번째 위치에 중복 위반이 붙는다.

    테스트 코드: RC-011
    """
    # when: [1, 2, 1] 값으로 검증한다
    found = chart_issues(ONE, raw_chart("bar", 0, [1, 2, 1]))

    # then: `["chart","values",2]` chart-value-duplicate 하나뿐이다
    assert found == [(("chart", "values", 2), "chart-value-duplicate")]


def test_value_count_follows_the_kind_rule() -> None:
    """값 개수는 종류 규칙을 따르고 계열이 있으면 정확히 1개다.

    테스트 코드: RC-012
    """

    def count_issue(
        definition: RawReportDefinition, kind: str, values: list[int], series: int | None = None
    ) -> bool:
        found = chart_issues(definition, raw_chart(kind, 0, values, series=series))
        return (("chart", "values"), "chart-values-count") in found

    # when: 종류별로 규칙 밖 개수의 값을 주고 검증한다
    results = [
        count_issue(ONE, "pie", [1, 2]),
        count_issue(ONE, "doughnut", [1, 2]),
        count_issue(ONE, "scatter", [1]),
        count_issue(ONE, "combo", [1]),
        count_issue(ONE, "combo", list(range(1, 12))),
        count_issue(ONE, "bar", list(range(1, 12))),
        count_issue(TWO, "bar", [2, 3], series=1),  # 계열이 있으면 값은 정확히 1개
    ]

    # then: 원형·분산형·콤보·막대의 개수 위반이 있고 계열이 있으면 2개도 위반이다
    assert all(results)


def test_value_count_boundaries_are_accepted() -> None:
    """규칙 경계의 값 개수(콤보 2·10, 막대 10, 분산형 2·3)는 받아들인다.

    테스트 코드: RC-012
    """
    # when: 경계 개수의 값으로 각각 검증한다
    counts = [
        len(_parse(ONE, raw_chart("combo", 0, [1, 2])).values),
        len(_parse(ONE, raw_chart("combo", 0, list(range(1, 11)))).values),
        len(_parse(ONE, raw_chart("bar", 0, list(range(1, 11)))).values),
        len(_parse(ONE, raw_chart("scatter", 0, [3, 1])).values),
        len(_parse(ONE, raw_chart("scatter", 0, [3, 1, 2])).values),  # 다중 Y 계열
    ]

    # then: 값 개수가 입력 그대로다
    assert counts == [2, 10, 10, 2, 3]


def test_eleven_values_are_a_single_count_violation() -> None:
    """값이 11개면 개수 위반 하나뿐이다.

    테스트 코드: RC-013
    """
    # when: 값 11개로 막대 차트를 검증한다
    found = chart_issues(ONE, raw_chart("bar", 0, list(range(1, 12))))

    # then: `["chart","values"]` chart-values-count 하나뿐이다
    assert found == [(("chart", "values"), "chart-values-count")]


@pytest.mark.parametrize("size", [12, 1000, 100_000])
def test_a_huge_value_list_records_one_violation_not_one_per_item(size: int) -> None:
    """값 목록이 아무리 커도 위반은 하나뿐이다.

    테스트 코드: RC-013
    """
    # when: 항목마다 값 열이 아닌 값이 12~100,000개인 목록으로 막대 차트를 검증한다 (전제: 항목별
    #   위반이 쌓이면 응답이 커진다)
    # 0은 그룹 컬럼이라 항목마다 값 열이 아니다: 항목별 위반이 쌓이면 응답이 커진다
    found = chart_issues(ONE, raw_chart("bar", 0, [0] * size))

    # then: 항목별 위반 없이 chart-values-count 하나뿐이다
    assert found == [(("chart", "values"), "chart-values-count")]


def test_an_empty_value_list_is_a_count_violation() -> None:
    """빈 값 목록도 개수 위반이다.

    테스트 코드: RC-012
    """
    # when: 값이 빈 목록인 차트를 검증한다
    found = chart_issues(ONE, raw_chart("bar", 0, []))

    # then: chart-values-count 하나뿐이다
    assert found == [(("chart", "values"), "chart-values-count")]


def test_value_order_is_kept() -> None:
    """값은 받은 순서 그대로 보관한다.

    테스트 코드: RC-011
    """
    # when: [3, 1, 2] 순서의 콤보 값을 검증한다
    settings = _parse(ONE, raw_chart("combo", 0, [3, 1, 2]))

    # then: 값 순서가 (3, 1, 2)다
    assert settings.values == (3, 1, 2)


@pytest.mark.parametrize("kind", ["pie", "doughnut", "scatter", "combo"])
def test_swap_is_rejected_where_not_allowed(kind: str) -> None:
    """행/열 전환을 허용하지 않는 종류에 swap을 켜면 거절한다.

    테스트 코드: RC-015
    """
    # given: 종류에 맞는 값 목록
    values = [1, 2] if kind in {"scatter", "combo"} else [1]
    # when: swap을 켜고 검증한다
    found = chart_issues(ONE, raw_chart(kind, 0, values, swap=True))

    # then: `["chart","swap"]` chart-swap-invalid 하나뿐이다
    assert found == [(("chart", "swap"), "chart-swap-invalid")]


@pytest.mark.parametrize("kind", BAR_LIKE)
def test_swap_is_accepted_for_bar_like_kinds(kind: str) -> None:
    """막대형·꺾은선·영역은 swap을 켤 수 있다.

    테스트 코드: RC-015
    """
    # when: swap true로 검증한다
    settings = _parse(ONE, raw_chart(kind, 0, [1], swap=True))

    # then: swap이 켜진 채 통과한다
    assert settings.swap is True


@pytest.mark.parametrize("swap", ["true", 1, 0, None])
def test_swap_must_be_a_boolean(swap: object) -> None:
    """swap이 bool이 아니면 chart-swap-invalid다.

    테스트 코드: RC-015
    """
    # when: 문자열·숫자·null swap으로 검증한다
    found = chart_issues(ONE, raw_chart("bar", 0, [1], swap=swap))

    # then: `["chart","swap"]` chart-swap-invalid 하나뿐이다
    assert found == [(("chart", "swap"), "chart-swap-invalid")]


@pytest.mark.parametrize("kind", [k for k in ALL_KINDS if k != "combo"])
def test_secondary_axis_is_rejected_outside_combo(kind: str) -> None:
    """콤보가 아닌 종류에 보조 축을 켜면 chart-secondary-invalid다.

    테스트 코드: RC-015
    """
    # when: 보조 축을 켠 차트를 종류별로 검증한다
    found = chart_issues(ONE, _with(_minimal(kind), secondary_axis=True))

    # then: `["chart","secondary_axis"]` chart-secondary-invalid 하나뿐이다
    assert found == [(("chart", "secondary_axis"), "chart-secondary-invalid")]


def test_secondary_axis_is_accepted_for_combo() -> None:
    """콤보는 보조 축을 켤 수 있다.

    테스트 코드: RC-015
    """
    # when: 보조 축을 켠 콤보를 검증한다
    settings = _parse(ONE, raw_chart("combo", 0, [1, 2], secondary_axis=True))

    # then: secondary_axis가 켜진 채 통과한다
    assert settings.secondary_axis is True


@pytest.mark.parametrize("flag", ["yes", 1, 0, None])
@pytest.mark.parametrize("key", ["data_labels", "secondary_axis"])
def test_flags_must_be_booleans(key: str, flag: object) -> None:
    """data_labels·secondary_axis가 bool이 아니면 chart-flag-invalid다.

    테스트 코드: RC-015
    """
    # when: 문자열·숫자·null 켜기·끄기 값으로 검증한다
    found = chart_issues(ONE, raw_chart("bar", 0, [1], **{key: flag}))

    # then: 해당 키에 chart-flag-invalid 하나뿐이다
    assert found == [(("chart", key), "chart-flag-invalid")]


def _with(chart: Any, **changes: Any) -> Any:  # noqa: ANN401 - RawChart
    import dataclasses  # noqa: PLC0415

    return dataclasses.replace(chart, **changes)


@pytest.mark.parametrize("key", TEXT_KEYS)
def test_texts_are_trimmed(key: str) -> None:
    """글자 칸은 앞뒤 공백을 지워 저장한다.

    테스트 코드: RC-016
    """
    # when: 앞뒤 공백과 줄바꿈이 있는 글자로 검증한다
    settings = _parse(ONE, raw_chart("bar", 0, [1], **{key: "  제목 \n"}))

    # then: 공백이 지워진 글자다
    assert getattr(settings, key) == "제목"


@pytest.mark.parametrize("key", TEXT_KEYS)
def test_text_of_one_hundred_characters_is_accepted(key: str) -> None:
    """글자 100자는 받아들인다.

    테스트 코드: RC-016
    """
    # when: 100자 글자로 검증한다
    settings = _parse(ONE, raw_chart("bar", 0, [1], **{key: "가" * 100}))

    # then: 그대로 보관된다
    assert getattr(settings, key) == "가" * 100


@pytest.mark.parametrize("key", TEXT_KEYS)
def test_spaces_around_a_hundred_characters_do_not_count(key: str) -> None:
    """앞뒤 공백은 100자 한도에 세지 않는다.

    테스트 코드: RC-016
    """
    # when: 앞뒤 공백 둘씩 붙은 100자로 검증한다
    settings = _parse(ONE, raw_chart("bar", 0, [1], **{key: f"  {'a' * 100}  "}))

    # then: 공백 없는 100자로 보관된다
    assert getattr(settings, key) == "a" * 100


@pytest.mark.parametrize("key", TEXT_KEYS)
@pytest.mark.parametrize("text", ["가" * 101, "a\x00b", 1, None, ["x"]])
def test_invalid_texts_are_rejected_at_their_key(key: str, text: object) -> None:
    """101자·NUL 문자·문자열이 아닌 값은 그 키의 chart-text-invalid다.

    테스트 코드: RC-016
    """
    # when: 101자·NUL 포함·숫자·null·목록 글자로 검증한다
    found = chart_issues(ONE, raw_chart("bar", 0, [1], **{key: text}))

    # then: 해당 키에 chart-text-invalid 하나뿐이다
    assert found == [(("chart", key), "chart-text-invalid")]


def test_blank_text_becomes_empty() -> None:
    """공백만 있는 글자는 빈 글자가 된다.

    테스트 코드: RC-016
    """
    # when: 공백만 있는 제목으로 검증한다
    settings = _parse(ONE, raw_chart("bar", 0, [1], title="   "))

    # then: 제목이 빈 글자다
    assert settings.title == ""


@pytest.mark.parametrize("legend", ["top", "right", "bottom", "none"])
def test_legend_accepts_four_positions(legend: str) -> None:
    """범례는 top·right·bottom·none 네 위치를 받는다.

    테스트 코드: RC-017
    """
    # when: 네 위치로 각각 검증한다
    settings = _parse(ONE, raw_chart("bar", 0, [1], legend=legend))

    # then: 범례 위치가 그대로다
    assert settings.legend == LegendPosition(legend)


@pytest.mark.parametrize("legend", ["left", "TOP", " top", "", None, 1, True])
def test_legend_rejects_anything_else(legend: object) -> None:
    """네 위치 밖의 범례 값은 chart-legend-invalid다.

    테스트 코드: RC-017
    """
    # when: left·대문자·공백 포함·빈 글자·null·숫자로 검증한다
    found = chart_issues(ONE, raw_chart("bar", 0, [1], legend=legend))

    # then: `["chart","legend"]` chart-legend-invalid 하나뿐이다
    assert found == [(("chart", "legend"), "chart-legend-invalid")]


@pytest.mark.parametrize("key", ["value_min", "value_max"])
@pytest.mark.parametrize("number", [True, False, "10", float("inf"), float("-inf"), float("nan")])
def test_range_rejects_non_numbers_and_non_finite(key: str, number: object) -> None:
    """축 범위가 bool·문자열·무한대·NaN이면 chart-range-invalid다.

    테스트 코드: RC-018
    """
    # when: 숫자가 아니거나 유한하지 않은 범위 값으로 검증한다
    found = chart_issues(ONE, raw_chart("bar", 0, [1], **{key: number}))

    # then: 해당 키에 chart-range-invalid 하나뿐이다
    assert found == [(("chart", key), "chart-range-invalid")]


@pytest.mark.parametrize("key", ["value_min", "value_max"])
@pytest.mark.parametrize("number", [2**53, -(2**53), 10**30])
def test_range_rejects_numbers_beyond_the_safe_integer(key: str, number: int) -> None:
    """축 범위의 절댓값이 2^53-1을 넘으면 chart-range-invalid다.

    테스트 코드: RC-018
    """
    # when: 2^53 이상 범위 값으로 검증한다
    found = chart_issues(ONE, raw_chart("bar", 0, [1], **{key: number}))

    # then: 해당 키에 chart-range-invalid 하나뿐이다
    assert found == [(("chart", key), "chart-range-invalid")]


@pytest.mark.parametrize("key", ["value_min", "value_max"])
@pytest.mark.parametrize("number", [10**400, -(10**400), 10**309, -(10**309)])
def test_range_rejects_integers_too_large_for_a_float_without_raising(
    key: str, number: int
) -> None:
    """실수로 바꿀 수 없을 만큼 큰 정수도 예외 없이 chart-range-invalid다.

    테스트 코드: RC-018
    """
    # when: 10^309·10^400 같은 큰 정수 범위로 검증한다
    found = chart_issues(ONE, raw_chart("bar", 0, [1], **{key: number}))

    # then: 오류 없이 해당 키에 chart-range-invalid 하나뿐이다
    assert found == [(("chart", key), "chart-range-invalid")]


def test_range_accepts_integers_floats_and_the_safe_limits() -> None:
    """축 범위는 정수·소수·안전 정수 한계값을 받는다.

    테스트 코드: RC-018
    """
    # given: 안전 정수 한계
    limit = 2**53 - 1

    # when: ±한계 범위와 소수 범위로 각각 검증한다
    settings = _parse(ONE, raw_chart("bar", 0, [1], value_min=-limit, value_max=limit))
    decimal = _parse(ONE, raw_chart("bar", 0, [1], value_min=-1.5, value_max=0.25))

    # then: 범위 값이 그대로다
    assert (settings.value_min, settings.value_max) == (-limit, limit)
    assert (decimal.value_min, decimal.value_max) == (-1.5, 0.25)


def test_range_with_only_one_side_is_accepted() -> None:
    """한쪽만 준 축 범위도 받는다.

    테스트 코드: RC-018
    """
    # when: 최소만, 최대만 준 차트를 각각 검증한다
    only_min = _parse(ONE, raw_chart("bar", 0, [1], value_min=0))
    only_max = _parse(ONE, raw_chart("bar", 0, [1], value_max=0))

    # then: 반대쪽은 null이다
    assert only_min.value_max is None
    assert only_max.value_min is None


@pytest.mark.parametrize(("low", "high"), [(5, 5), (6, 5), (0.5, 0.5), (1, 0.5)])
def test_range_min_must_be_below_max(low: float, high: float) -> None:
    """최소가 최대 이상이면 value_max에 chart-range-order다.

    테스트 코드: RC-018
    """
    # when: 최소 ≥ 최대인 범위로 검증한다
    found = chart_issues(ONE, raw_chart("bar", 0, [1], value_min=low, value_max=high))

    # then: `["chart","value_max"]` chart-range-order 하나뿐이다
    assert found == [(("chart", "value_max"), "chart-range-order")]


@pytest.mark.parametrize("kind", ["pie", "doughnut"])
@pytest.mark.parametrize("key", ["value_min", "value_max"])
def test_range_is_rejected_where_the_kind_has_no_value_axis(kind: str, key: str) -> None:
    """값 축이 없는 원형·도넛형에 범위를 주면 chart-range-invalid다.

    테스트 코드: RC-019
    """
    # when: 범위를 준 원형·도넛형을 검증한다
    found = chart_issues(ONE, raw_chart(kind, 0, [1], **{key: 10}))

    # then: 해당 키에 chart-range-invalid 하나뿐이다
    assert found == [(("chart", key), "chart-range-invalid")]


@pytest.mark.parametrize("kind", ["scatter", "combo"])
def test_range_is_accepted_for_scatter_and_combo(kind: str) -> None:
    """분산형·콤보는 축 범위를 받는다.

    테스트 코드: RC-019
    """
    # when: 범위를 준 분산형·콤보를 검증한다
    settings = _parse(ONE, raw_chart(kind, 0, [1, 2], value_min=0, value_max=10))

    # then: 범위가 그대로다
    assert (settings.value_min, settings.value_max) == (0, 10)


@pytest.mark.parametrize(
    ("key", "number"),
    [("value_min", -1), ("value_min", 101), ("value_max", -1), ("value_max", 101)],
)
def test_percent_stack_range_must_stay_between_zero_and_hundred(key: str, number: int) -> None:
    """100% 누적의 범위는 0~100 밖이면 chart-range-invalid다.

    테스트 코드: RC-019
    """
    # when: -1·101 범위로 검증한다
    found = chart_issues(ONE, raw_chart("stacked_100_bar", 0, [1], **{key: number}))

    # then: 해당 키에 chart-range-invalid 하나뿐이다
    assert found == [(("chart", key), "chart-range-invalid")]


def test_percent_stack_range_accepts_zero_to_hundred() -> None:
    """100% 누적은 0~100 안의 범위를 받는다.

    테스트 코드: RC-019
    """
    # when: 0~100과 10.5~99.5 범위로 각각 검증한다
    settings = _parse(ONE, raw_chart("stacked_100_bar", 0, [1], value_min=0, value_max=100))
    inner = _parse(ONE, raw_chart("stacked_100_bar", 0, [1], value_min=10.5, value_max=99.5))

    # then: 범위가 그대로다
    assert (settings.value_min, settings.value_max) == (0, 100)
    assert (inner.value_min, inner.value_max) == (10.5, 99.5)


def test_all_chart_issues_are_reported_together() -> None:
    """차트 위반은 모두 모아서 알린다.

    테스트 코드: RC-030
    """
    # given: 범주·값·범례가 함께 틀린 차트
    chart = raw_chart("bar", 1, [0], legend="left")  # 범주·값·범례가 함께 틀림

    # when: 차트를 검증한다
    with pytest.raises(ReportDefinitionError) as caught:
        _parse(ONE, chart)

    # then: 세 위반이 위치·코드와 함께 모두 나오고 예외 문구는 첫 위반 문구다
    issues = caught.value.issues
    assert {(tuple(i.location), i.code) for i in issues} == {
        (("chart", "category"), "chart-category-invalid"),
        (("chart", "values", 0), "chart-value-invalid"),
        (("chart", "legend"), "chart-legend-invalid"),
    }
    assert len(issues) == 3
    assert str(caught.value) == issues[0].message


def test_every_issue_has_a_korean_message() -> None:
    """모든 위반은 한국어 문구를 가진다.

    테스트 코드: RC-030
    """
    # when: 범주·값·범례·제목이 함께 틀린 차트를 검증한다
    with pytest.raises(ReportDefinitionError) as caught:
        _parse(ONE, raw_chart("bar", 1, [0], legend="left", title="가" * 101))

    # then: 모든 위반 문구가 한국어다
    assert all(i.message and i.message.isascii() is False for i in caught.value.issues)


def test_kind_dependent_checks_are_skipped_for_an_unknown_kind() -> None:
    """모르는 종류면 종류에 따른 검사는 건너뛴다.

    테스트 코드: RC-005
    """
    # given: 전환·보조 축·범위·값 5개를 함께 준 모르는 종류의 차트
    chart = raw_chart(
        "nope", 0, [1, 2, 3, 4, 5], swap=True, secondary_axis=True, value_min=0, value_max=10
    )

    # when: 차트를 검증한다
    found = chart_issues(ONE, chart)

    # then: 종류 위반 하나뿐이다
    assert found == [(("chart", "kind"), "chart-kind-invalid")]


def test_series_rules_are_skipped_for_an_unknown_kind() -> None:
    """모르는 종류면 계열 필수 검사도 건너뛴다.

    테스트 코드: RC-005
    """
    # when: 모르는 종류에 계열 없이 검증한다 (전제: 그룹이 2개인 정의)
    found = chart_issues(TWO, raw_chart("nope", 0, [2]))  # 그룹 2개인데 계열이 없지만

    # then: 종류 위반 하나뿐이다
    assert found == [(("chart", "kind"), "chart-kind-invalid")]


def test_kind_independent_checks_still_run_for_an_unknown_kind() -> None:
    """모르는 종류여도 종류와 무관한 검사(범주·값·범례)는 한다.

    테스트 코드: RC-005
    """
    # when: 모르는 종류에 범주·값·범례도 틀린 차트를 검증한다
    found = chart_issues(ONE, raw_chart("nope", 5, [0], legend="left"))

    # then: 종류·범주·값·범례 위반이 모두 나온다
    assert {code for _, code in found} == {
        "chart-kind-invalid",
        "chart-category-invalid",
        "chart-value-invalid",
        "chart-legend-invalid",
    }


def test_to_raw_is_normalized_and_parses_to_the_same_settings() -> None:
    """정규화한 차트는 공백이 지워지고 다시 검증해도 같은 설정이다.

    테스트 코드: RC-029
    """
    # given: 글자에 앞뒤 공백이 붙은 누적 막대 차트
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
    # when: 차트를 검증한 뒤 설정을 원시 차트로 되돌린다
    settings = _parse(TWO, chart)

    normalized = settings.to_raw()

    # then: 글자 공백이 지워지고 재검증하면 같은 설정이다
    assert normalized.title == "Vendor별"
    assert (normalized.category_axis_title, normalized.value_axis_title) == ("분기", "금액")
    assert normalized.kind == "stacked_bar"
    assert normalized.legend == "bottom"
    assert normalized.values == [2]
    assert _parse(TWO, normalized) == settings


def test_to_raw_fills_omitted_keys_with_defaults() -> None:
    """생략한 키는 정규화 값에서 기본값으로 채워진다.

    테스트 코드: RC-029
    """
    # when: 필수 키만 준 꺾은선 차트를 검증해 원시 차트로 되돌린다
    normalized = _parse(ONE, raw_chart("line", 0, [1])).to_raw()

    # then: 모든 선택 키가 기본값이다
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
