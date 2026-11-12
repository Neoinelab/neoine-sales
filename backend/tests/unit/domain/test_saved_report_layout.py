"""결과 배치 값: 파싱·위반 위치·JSON 왕복·기본값 대체."""

from typing import Any

import pytest

from app.domain.report.errors import ReportDefinitionError
from app.domain.saved_report.layout import (
    DEFAULT_LAYOUT,
    ResultTile,
    ResultView,
    TileArrange,
    layout_from_json,
    layout_to_json,
    parse_layout,
)
from tests.support.layout_defs import layout_json, make_layout, raw_layout


def _locations(raw: object) -> list[tuple[str | int, ...]]:
    with pytest.raises(ReportDefinitionError) as caught:
        parse_layout(raw)  # type: ignore[arg-type]
    return [tuple(i.location) for i in caught.value.issues]


def test_default_layout_is_both_table_then_chart_stacked() -> None:
    """기본 배치는 표+차트, 표 → 차트, 두 줄이다."""
    # when: 기본 배치의 세 값을 읽는다
    view, order, arrange = DEFAULT_LAYOUT.view, DEFAULT_LAYOUT.order, DEFAULT_LAYOUT.arrange
    # then: 명세와 같다
    assert view == ResultView.BOTH
    assert order == (ResultTile.TABLE, ResultTile.CHART)
    assert arrange == TileArrange.STACKED


def test_parse_layout_valid_values_returns_layout() -> None:
    """맞는 값의 원시 배치는 ReportLayout으로 해석된다."""
    # when: 차트만 / 차트 → 표 / 한 줄 배치를 해석한다
    parsed = parse_layout(raw_layout("chart", ("chart", "table"), "side_by_side"))
    # then: 같은 값의 ReportLayout이다
    assert parsed == make_layout("chart", ("chart", "table"), "side_by_side")
    assert parsed.order == (ResultTile.CHART, ResultTile.TABLE)


@pytest.mark.parametrize("view", ["both", "chart", "table"])
def test_parse_layout_accepts_every_view(view: str) -> None:
    """보기 방식 세 값을 모두 받는다."""
    # when: 배치를 해석한다
    parsed = parse_layout(raw_layout(view)).view
    # then: 보기 방식이 입력과 같다
    assert parsed == ResultView(view)


@pytest.mark.parametrize("arrange", ["side_by_side", "stacked"])
def test_parse_layout_accepts_every_arrange(arrange: str) -> None:
    """배치 두 값을 모두 받는다."""
    # when: 배치를 해석한다
    parsed = parse_layout(raw_layout(arrange=arrange)).arrange
    # then: 배치가 입력과 같다
    assert parsed == TileArrange(arrange)


@pytest.mark.parametrize("view", ["Both", "grid", "", " both", 1, None, ["both"]])
def test_parse_layout_unknown_view_reports_view_loc(view: object) -> None:
    """알 수 없는 보기 방식은 ["layout","view"] 위치의 위반이다."""
    # when: 배치를 해석한다
    locations = _locations(raw_layout(view=view))
    # then: view 위치 위반 하나다
    assert locations == [("layout", "view")]


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
    """table·chart를 한 번씩 담지 않은 순서는 ["layout","order"] 위치의 위반이다."""
    # when: 배치를 해석한다
    locations = _locations(raw_layout(order=order))
    # then: order 위치 위반 하나다
    assert locations == [("layout", "order")]


@pytest.mark.parametrize("arrange", ["row", "", "Stacked", 0, None])
def test_parse_layout_unknown_arrange_reports_arrange_loc(arrange: object) -> None:
    """알 수 없는 배치는 ["layout","arrange"] 위치의 위반이다."""
    # when: 배치를 해석한다
    locations = _locations(raw_layout(arrange=arrange))
    # then: arrange 위치 위반 하나다
    assert locations == [("layout", "arrange")]


def test_parse_layout_collects_all_issues() -> None:
    """세 값이 모두 틀리면 위반을 모두 모아 view, order, arrange 순서로 알린다.

    테스트 코드: RS-044
    """
    # when: 세 값이 모두 틀린 배치를 해석한다
    locations = _locations(raw_layout(view="x", order=["a", "b"], arrange="y"))
    # then: 세 위치 위반이 순서대로 있다
    assert locations == [("layout", "view"), ("layout", "order"), ("layout", "arrange")]


def test_parse_layout_issues_use_the_invalid_value_code() -> None:
    """배치 위반의 code는 invalid-value이고 문구가 있다."""
    # when: 틀린 배치를 해석한다
    with pytest.raises(ReportDefinitionError) as caught:
        parse_layout(raw_layout(view="x", order=["a"], arrange="y"))
    # then: 모든 위반이 invalid-value이고 문구가 비어 있지 않다
    assert {i.code for i in caught.value.issues} == {"invalid-value"}
    assert all(i.message for i in caught.value.issues)


def test_layout_json_round_trip() -> None:
    """배치를 JSON으로 바꿨다가 읽으면 같은 배치다."""
    # given: 표만 / 차트 → 표 / 한 줄 배치
    layout = make_layout("table", ("chart", "table"), "side_by_side")
    # when: JSON으로 바꾼다
    data = layout_to_json(layout)
    # then: 문자열 키·값의 JSON이고 다시 읽으면 같다
    assert data == layout_json("table", ("chart", "table"), "side_by_side")
    assert layout_from_json(data) == layout


def test_layout_to_json_uses_plain_strings_and_a_list() -> None:
    """JSON 변환은 일반 문자열과 list를 쓴다."""
    # when: 기본 배치를 JSON으로 바꾼다
    data = layout_to_json(DEFAULT_LAYOUT)
    # then: 일반 str 값과 list order다
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
    """저장된 배치가 NULL이거나 깨졌으면 오류 없이 기본 배치로 읽는다.

    테스트 코드: RS-039
    """
    # when: 저장된 JSON에서 배치를 읽는다
    layout = layout_from_json(data)
    # then: 기본 배치다
    assert layout == DEFAULT_LAYOUT
