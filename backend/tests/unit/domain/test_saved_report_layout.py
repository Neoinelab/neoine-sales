"""결과 배치 값(Reports 작성/결과 탭 분리 AC24~25, 27): 파싱·위반 위치·JSON 왕복·기본값 대체."""

from typing import Any

import pytest
from app.domain.saved_report.layout import (
    DEFAULT_LAYOUT,
    ResultTile,
    ResultView,
    TileArrange,
    layout_from_json,
    layout_to_json,
    parse_layout,
)

from app.domain.report.errors import ReportDefinitionError
from tests.support.layout_defs import layout_json, make_layout, raw_layout


def _locations(raw: object) -> list[tuple[str | int, ...]]:
    with pytest.raises(ReportDefinitionError) as caught:
        parse_layout(raw)  # type: ignore[arg-type]
    return [tuple(i.location) for i in caught.value.issues]


def test_default_layout_is_both_table_then_chart_stacked() -> None:
    assert DEFAULT_LAYOUT.view == ResultView.BOTH
    assert DEFAULT_LAYOUT.order == (ResultTile.TABLE, ResultTile.CHART)
    assert DEFAULT_LAYOUT.arrange == TileArrange.STACKED


def test_parse_layout_valid_values_returns_layout() -> None:
    parsed = parse_layout(raw_layout("chart", ("chart", "table"), "side_by_side"))

    assert parsed == make_layout("chart", ("chart", "table"), "side_by_side")
    assert parsed.order == (ResultTile.CHART, ResultTile.TABLE)


@pytest.mark.parametrize("view", ["both", "chart", "table"])
def test_parse_layout_accepts_every_view(view: str) -> None:
    assert parse_layout(raw_layout(view)).view == ResultView(view)


@pytest.mark.parametrize("arrange", ["side_by_side", "stacked"])
def test_parse_layout_accepts_every_arrange(arrange: str) -> None:
    assert parse_layout(raw_layout(arrange=arrange)).arrange == TileArrange(arrange)


@pytest.mark.parametrize("view", ["Both", "grid", "", " both", 1, None, ["both"]])
def test_parse_layout_unknown_view_reports_view_loc(view: object) -> None:
    assert _locations(raw_layout(view=view)) == [("layout", "view")]


@pytest.mark.parametrize(
    "order",
    [
        ["table", "table"],
        ["chart", "chart"],
        ["table"],
        [],
        ["table", "chart", "chart"],
        ["table", "chart", "x"],
        "table,chart",
        [1, 2],
        None,
        ["Table", "chart"],
    ],
)
def test_parse_layout_bad_order_reports_order_loc(order: object) -> None:
    assert _locations(raw_layout(order=order)) == [("layout", "order")]


@pytest.mark.parametrize("arrange", ["row", "", "Stacked", 0, None])
def test_parse_layout_unknown_arrange_reports_arrange_loc(arrange: object) -> None:
    assert _locations(raw_layout(arrange=arrange)) == [("layout", "arrange")]


def test_parse_layout_collects_all_issues() -> None:
    locations = _locations(raw_layout(view="x", order=["a", "b"], arrange="y"))

    assert locations == [("layout", "view"), ("layout", "order"), ("layout", "arrange")]


def test_parse_layout_issues_use_the_invalid_value_code() -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        parse_layout(raw_layout(view="x", order=["a"], arrange="y"))

    assert {i.code for i in caught.value.issues} == {"invalid-value"}
    assert all(i.message for i in caught.value.issues)


def test_layout_json_round_trip() -> None:
    layout = make_layout("table", ("chart", "table"), "side_by_side")

    data = layout_to_json(layout)

    assert data == layout_json("table", ("chart", "table"), "side_by_side")
    assert layout_from_json(data) == layout


def test_layout_to_json_uses_plain_strings_and_a_list() -> None:
    data = layout_to_json(DEFAULT_LAYOUT)

    assert data == {"view": "both", "order": ["table", "chart"], "arrange": "stacked"}
    assert type(data["view"]) is str
    assert type(data["order"]) is list


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        "both",
        {},
        {"view": "x", "order": ["table", "chart"], "arrange": "stacked"},
        {"order": ["table", "chart"], "arrange": "stacked"},
        {"view": "both", "arrange": "stacked"},
        {"view": "both", "order": ["table", "table"], "arrange": "stacked"},
        {"view": "both", "order": ["table", "chart"], "arrange": "row"},
        {"view": 1, "order": ["table", "chart"], "arrange": "stacked"},
    ],
)
def test_layout_from_json_null_or_broken_returns_default(data: Any) -> None:  # noqa: ANN401
    assert layout_from_json(data) == DEFAULT_LAYOUT
