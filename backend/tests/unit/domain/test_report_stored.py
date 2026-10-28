"""저장용 정의 JSON(계획 4.2 `domain/report/stored.py`): 원시 정의 <-> JSON, 사용 엔티티 판정.

저장 형식은 `/query` 요청과 같은 모양(snake_case)이고, 검증을 통과한 원시 정의 그대로다.
"""

import json
from typing import Any

import pytest

from app.domain.report.errors import ReportDefinitionError
from app.domain.report.stored import (
    definition_entities,
    definition_from_json,
    definition_to_json,
)
from app.domain.report.vocabulary import Entity
from tests.support.report_defs import VALID_CONDITIONS, col, cond, parse, raw


def _through_json(definition: Any) -> Any:  # noqa: ANN401 - RawReportDefinition
    """실제 저장처럼 JSON 문자열을 한 번 거친다(직렬화 불가한 값이면 여기서 실패한다)."""
    return definition_from_json(json.loads(json.dumps(definition_to_json(definition))))


def test_definition_json_has_the_query_request_shape() -> None:
    definition = raw(
        [
            col("deal.vendor", group=True, label="벤더"),
            col("deal.amount", aggregate="sum", format="krw_million", sort="desc"),
        ],
        [cond("deal.name", "contains", "abc")],
        combine="or",
        row_limit=100,
    )

    data = definition_to_json(definition)

    assert data == {
        "columns": [
            {
                "field": "deal.vendor",
                "label": "벤더",
                "format": None,
                "prefix_length": None,
                "group": True,
                "aggregate": None,
                "sort": None,
            },
            {
                "field": "deal.amount",
                "label": None,
                "format": "krw_million",
                "prefix_length": None,
                "group": False,
                "aggregate": "sum",
                "sort": "desc",
            },
        ],
        "conditions": [{"field": "deal.name", "operator": "contains", "value": "abc"}],
        "combine": "or",
        "row_limit": 100,
    }


def test_definition_json_writes_column_sort_and_no_top_level_sort() -> None:
    data: dict[str, Any] = definition_to_json(
        raw([col("deal.code"), col("deal.name", sort="desc")])
    )

    assert [c["sort"] for c in data["columns"]] == [None, "desc"]
    assert "sort" not in data


def test_stored_definition_round_trips_through_json() -> None:
    definition = raw(
        [col("deal.vendor", group=True), col("deal.amount", label="금액 합계")],
        [cond(field, operator, value) for field, operator, value in VALID_CONDITIONS],
        combine="or",
        row_limit=10000,
    )

    assert _through_json(definition) == definition


def test_round_trip_keeps_unset_display_names_unset() -> None:
    definition = raw([col("deal.code")])

    restored = _through_json(definition)

    assert restored.columns[0].label is None
    assert restored == definition


def test_round_tripped_definition_parses_to_the_same_definition() -> None:
    columns = [col("deal.vendor", group=True), col("deal.amount")]
    conditions = [
        cond("deal.expected_close", "relative", {"period": "this_year"}),
        cond("deal.amount", "between", [1, 10]),
    ]
    original = raw(columns, conditions)

    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415

    assert parse_report_definition(_through_json(original)) == parse(columns, conditions)


@pytest.mark.parametrize(
    "broken",
    [
        [],
        "text",
        None,
        {},
        {"columns": "deal.code"},
        {"columns": ["deal.code"]},
        {"columns": [{"label": "필드 없음"}]},
        {"columns": [{"field": "deal.code"}], "conditions": "x"},
        {"columns": [{"field": "deal.code"}], "conditions": [1]},
    ],
    ids=[
        "array",
        "string",
        "null",
        "no-columns",
        "columns-string",
        "column-string",
        "column-without-field",
        "conditions-string",
        "condition-number",
    ],
)
def test_broken_stored_json_raises_stored_invalid(broken: object) -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        definition_from_json(broken)

    (issue,) = caught.value.issues
    assert issue.location == ("definition",)
    assert issue.code == "stored-invalid"
    assert issue.message == "저장된 리포트 정의를 읽을 수 없습니다."


def _entities(columns: list[dict[str, Any]], conditions: list[dict[str, Any]] | None = None) -> Any:  # noqa: ANN401
    return definition_entities(raw(columns, conditions or []))


def test_deal_only_definition_uses_the_deal_entity() -> None:
    assert _entities([col("deal.code")], [cond("deal.name", "contains", "a")]) == (Entity.DEAL,)


def test_action_column_adds_the_action_entity_after_deal() -> None:
    assert _entities([col("deal.code"), col("action.type")]) == (Entity.DEAL, Entity.ACTION)


def test_action_condition_alone_adds_the_action_entity() -> None:
    assert _entities([col("deal.code")], [cond("action.type", "in", [1])]) == (
        Entity.DEAL,
        Entity.ACTION,
    )


def test_action_only_columns_still_list_deal_first() -> None:
    assert _entities([col("action.type", group=True), col("action.count")]) == (
        Entity.DEAL,
        Entity.ACTION,
    )


def test_unknown_field_keys_are_ignored() -> None:
    assert _entities([col("deal.code"), col("nope.field")], [cond("x.y", "eq", 1)]) == (
        Entity.DEAL,
    )


# ---- 예전 포맷 자동 변환 (2026-10-28) ----


def _stored(*columns: dict[str, Any]) -> dict[str, Any]:
    return {"columns": list(columns), "conditions": [], "combine": "and", "row_limit": 1000}


@pytest.mark.parametrize("legacy", ["as_is", "name", "key"])
def test_legacy_formats_are_upgraded_when_read(legacy: str) -> None:
    stored = _stored(col("deal.name", format=legacy))

    column = definition_from_json(stored).columns[0]

    assert (column.format, column.prefix_length) == (None, None)


def test_legacy_prefix_becomes_prefix_option() -> None:
    stored = _stored(col("deal.name", format="prefix", prefix_length=7))

    column = definition_from_json(stored).columns[0]

    assert (column.format, column.prefix_length) == (None, 7)


def test_current_formats_are_kept_when_read() -> None:
    stored = _stored(
        col("deal.amount", format="thousands"),
        col("deal.expected_close", format="quarter"),
        col("deal.name"),
    )

    columns = definition_from_json(stored).columns

    assert [c.format for c in columns] == ["thousands", "quarter", None]


def test_upgraded_definition_parses_and_writes_new_shape() -> None:
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415

    stored = _stored(
        col("deal.name", format="as_is"),
        col("deal.owner", format="name"),
        col("deal.status", format="key"),
        col("deal.code", format="prefix", prefix_length=4),
        col("deal.amount", format="thousands"),
    )

    upgraded = definition_from_json(stored)
    parsed = parse_report_definition(upgraded)
    written: Any = definition_to_json(upgraded)

    assert [c.prefix_length for c in parsed.columns] == [None, None, None, 4, None]
    assert [c["format"] for c in written["columns"]] == [None, None, None, None, "thousands"]
    assert written["columns"][3]["prefix_length"] == 4
    assert not {"as_is", "prefix", "name", "key"} & {c["format"] for c in written["columns"]}


# ---- 컬럼별 정렬 (2026-10-28) ----


def test_column_sort_round_trips_through_json() -> None:
    definition = raw(
        [col("deal.name", sort="asc"), col("deal.vendor", sort="desc"), col("deal.code")]
    )

    assert _through_json(definition) == definition


def _with_top_sort(top: object, n: int = 3) -> dict[str, Any]:
    names = ["deal.code", "deal.name", "deal.vendor"][:n]
    stored = _stored(*[col(name) for name in names])
    stored["sort"] = top
    return stored


def test_legacy_top_level_sort_moves_to_that_column() -> None:
    stored = _with_top_sort({"column": 1, "direction": "desc"})

    columns = definition_from_json(stored).columns

    assert [c.sort for c in columns] == [None, "desc", None]


def test_legacy_sort_without_direction_is_ascending() -> None:
    columns = definition_from_json(_with_top_sort({"column": 0})).columns

    assert [c.sort for c in columns] == ["asc", None, None]


def test_legacy_null_sort_means_no_sort() -> None:
    columns = definition_from_json(_with_top_sort(None)).columns

    assert [c.sort for c in columns] == [None, None, None]


@pytest.mark.parametrize(
    "broken",
    [
        "x",
        {"column": 5},
        {"column": 3},
        {"column": -1},
        {"column": "0"},
        {"column": True},
        {"column": 0, "direction": 1},
    ],
    ids=[
        "string",
        "out-of-range",
        "equal-to-length",
        "negative",
        "text-index",
        "bool-index",
        "number-direction",
    ],
)
def test_broken_legacy_sort_is_stored_invalid(broken: object) -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        definition_from_json(_with_top_sort(broken))

    (issue,) = caught.value.issues
    assert issue.code == "stored-invalid"


def test_legacy_sort_with_unknown_direction_is_reported_when_run() -> None:
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415

    restored = definition_from_json(_with_top_sort({"column": 1, "direction": "up"}))

    with pytest.raises(ReportDefinitionError) as caught:
        parse_report_definition(restored)

    assert [(tuple(i.location), i.code) for i in caught.value.issues] == [
        (("columns", 1, "sort"), "sort-invalid")
    ]


def test_column_own_sort_wins_over_legacy_sort() -> None:
    stored = _stored(col("deal.code"), col("deal.name", sort="asc"))
    stored["sort"] = {"column": 1, "direction": "desc"}

    columns = definition_from_json(stored).columns

    assert columns[1].sort == "asc"


def test_column_empty_sort_is_kept_over_legacy_sort() -> None:
    stored = _stored(col("deal.code"), col("deal.name", sort=""))
    stored["sort"] = {"column": 1, "direction": "desc"}

    columns = definition_from_json(stored).columns

    assert columns[1].sort == ""


def test_non_text_column_sort_is_stored_invalid() -> None:
    stored = _stored(col("deal.code", sort=1))

    with pytest.raises(ReportDefinitionError) as caught:
        definition_from_json(stored)

    assert caught.value.issues[0].code == "stored-invalid"


def test_upgraded_legacy_sort_is_written_in_the_new_shape() -> None:
    upgraded = definition_from_json(_with_top_sort({"column": 2, "direction": "desc"}))

    written: Any = definition_to_json(upgraded)

    assert "sort" not in written
    assert [c["sort"] for c in written["columns"]] == [None, None, "desc"]
