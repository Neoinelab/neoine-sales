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
            col("deal.amount", aggregate="sum", format="krw_million"),
        ],
        [cond("deal.name", "contains", "abc")],
        combine="or",
        sort={"column": 1, "direction": "desc"},
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
            },
            {
                "field": "deal.amount",
                "label": None,
                "format": "krw_million",
                "prefix_length": None,
                "group": False,
                "aggregate": "sum",
            },
        ],
        "conditions": [{"field": "deal.name", "operator": "contains", "value": "abc"}],
        "combine": "or",
        "sort": {"column": 1, "direction": "desc"},
        "row_limit": 100,
    }


def test_definition_json_has_null_sort_when_there_is_none() -> None:
    assert definition_to_json(raw([col("deal.code")]))["sort"] is None


def test_stored_definition_round_trips_through_json() -> None:
    definition = raw(
        [col("deal.vendor", group=True), col("deal.amount", label="금액 합계")],
        [cond(field, operator, value) for field, operator, value in VALID_CONDITIONS],
        combine="or",
        sort={"column": 1, "direction": "desc"},
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
