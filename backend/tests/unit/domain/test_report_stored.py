"""저장용 정의 JSON(`domain/report/stored.py`).

원시 정의 <-> JSON, 사용 엔티티 판정, 예전 형식 읽기 변환을 본다.

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
    """저장 정의 JSON은 조회 요청과 같은 모양(컬럼 7키, 조건, 결합, 행 수)이다.

    테스트 코드: RQ-108
    """
    # given: 표시 이름·그룹·집계·정렬이 있는 정의
    definition = raw(
        [
            col("deal.vendor", group=True, label="벤더"),
            col("deal.amount", aggregate="sum", sort="desc"),
        ],
        [cond("deal.name", "contains", "abc")],
        combine="or",
        row_limit=100,
    )

    # when: 정의를 JSON으로 쓴다
    data = definition_to_json(definition)

    # then: 컬럼마다 7개 키와 conditions·combine·row_limit이다
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
                "format": None,
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
    """정렬은 컬럼에 쓰고 최상위 sort는 쓰지 않는다.

    테스트 코드: RQ-108
    """
    # when: 둘째 컬럼에 정렬이 있는 정의를 JSON으로 쓴다
    data: dict[str, Any] = definition_to_json(
        raw([col("deal.code"), col("deal.name", sort="desc")])
    )

    # then: 컬럼 sort는 [None, "desc"]이고 최상위 sort가 없다
    assert [c["sort"] for c in data["columns"]] == [None, "desc"]
    assert "sort" not in data


def test_stored_definition_round_trips_through_json() -> None:
    """모든 조건 모양을 가진 정의를 JSON으로 쓰고 읽으면 같다.

    테스트 코드: RQ-108
    """
    # given: 허용 조건 모양을 모두 가진 정의
    definition = raw(
        [col("deal.vendor", group=True), col("deal.amount", label="금액 합계")],
        [cond(field, operator, value) for field, operator, value in VALID_CONDITIONS],
        combine="or",
        row_limit=10000,
    )

    # when: JSON 문자열을 거쳐 다시 읽는다
    reloaded = _through_json(definition)
    # then: 처음 정의와 같다
    assert reloaded == definition


def test_round_trip_keeps_unset_display_names_unset() -> None:
    """생략한 표시 이름은 다시 읽어도 생략 그대로다.

    테스트 코드: RQ-108
    """
    # given: 표시 이름을 생략한 정의
    definition = raw([col("deal.code")])

    # when: JSON으로 쓰고 다시 읽는다
    restored = _through_json(definition)

    # then: 표시 이름은 None이고 정의는 같다
    assert restored.columns[0].label is None
    assert restored == definition


def test_round_tripped_definition_parses_to_the_same_definition() -> None:
    """다시 읽은 정의의 검증 결과는 처음 정의의 검증 결과와 같다.

    테스트 코드: RQ-108
    """
    # given: 그룹·상대 기간·범위 조건이 있는 정의
    columns = [col("deal.vendor", group=True), col("deal.amount")]
    conditions = [
        cond("deal.expected_close", "relative", {"period": "this_year"}),
        cond("deal.amount", "between", [1, 10]),
    ]
    original = raw(columns, conditions)

    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415

    # when: 다시 읽은 정의를 검증한다
    reloaded = parse_report_definition(_through_json(original))
    # then: 처음 정의의 검증 결과와 같다
    assert reloaded == parse(columns, conditions)


@pytest.mark.parametrize("period", ["last_1_month", "last_3_months", "last_6_months"])
def test_month_based_relative_period_survives_json_round_trip_and_parsing(period: str) -> None:
    """최근 1·3·6개월 상대 기간은 JSON을 거쳐도 그대로 검증된다.

    테스트 코드: RQ-108
    """
    # given: 개월 상대 기간 조건이 있는 정의 (매개변수)
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415

    columns = [col("deal.code")]
    conditions = [cond("deal.expected_close", "relative", {"period": period})]
    original = raw(columns, conditions)

    # when: JSON으로 쓰고 다시 읽는다
    restored = _through_json(original)

    # then: 읽은 정의가 같고 검증 결과도 같다
    assert restored == original
    assert parse_report_definition(restored) == parse(columns, conditions)


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
    """읽을 수 없는 저장 JSON은 stored-invalid 위반 하나와 고정 문구다.

    테스트 코드: RQ-112
    """
    # when·then: 깨진 JSON을 읽으면 ReportDefinitionError가 난다 (전제: 깨진 모양 매개변수)
    with pytest.raises(ReportDefinitionError) as caught:
        definition_from_json(broken)

    # then: 위치 ["definition"]의 stored-invalid 하나와 고정 문구다
    (issue,) = caught.value.issues
    assert issue.location == ("definition",)
    assert issue.code == "stored-invalid"
    assert issue.message == "저장된 리포트 정의를 읽을 수 없습니다."


def _entities(columns: list[dict[str, Any]], conditions: list[dict[str, Any]] | None = None) -> Any:  # noqa: ANN401
    return definition_entities(raw(columns, conditions or []))


def test_deal_only_definition_uses_the_deal_entity() -> None:
    """Deal 필드만 쓰는 정의는 Deal 엔터티만 쓴다."""
    # when: 사용 엔터티를 구한다
    entities = _entities([col("deal.code")], [cond("deal.name", "contains", "a")])
    # then: (Deal,)이다
    assert entities == (Entity.DEAL,)


def test_action_column_adds_the_action_entity_after_deal() -> None:
    """Action 컬럼이 있으면 Deal 다음에 Action 엔터티가 붙는다."""
    # when: 사용 엔터티를 구한다
    entities = _entities([col("deal.code"), col("action.type")])
    # then: (Deal, Action)이다
    assert entities == (Entity.DEAL, Entity.ACTION)


def test_action_condition_alone_adds_the_action_entity() -> None:
    """Action 조건만 있어도 Action 엔터티가 붙는다."""
    # when: 사용 엔터티를 구한다
    entities = _entities([col("deal.code")], [cond("action.type", "in", [1])])
    # then: (Deal, Action)이다
    assert entities == (Entity.DEAL, Entity.ACTION)


def test_action_only_columns_still_list_deal_first() -> None:
    """Action 컬럼만 있어도 Deal 엔터티가 먼저 나온다."""
    # when: 사용 엔터티를 구한다
    entities = _entities([col("action.type", group=True), col("action.count")])
    # then: (Deal, Action) 순서다
    assert entities == (Entity.DEAL, Entity.ACTION)


def test_unknown_field_keys_are_ignored() -> None:
    """모르는 필드 key는 엔터티 판정에서 무시한다."""
    # when: 사용 엔터티를 구한다
    entities = _entities([col("deal.code"), col("nope.field")], [cond("x.y", "eq", 1)])
    # then: (Deal,)뿐이다
    assert entities == (Entity.DEAL,)


# ---- 예전 포맷 자동 변환 ----


def _stored(*columns: dict[str, Any]) -> dict[str, Any]:
    return {"columns": list(columns), "conditions": [], "combine": "and", "row_limit": 1000}


@pytest.mark.parametrize("legacy", ["as_is", "name", "key"])
def test_legacy_formats_are_upgraded_when_read(legacy: str) -> None:
    """예전 텍스트·코드 포맷(as_is·name·key)은 읽을 때 포맷 없음이 된다.

    테스트 코드: RQ-109
    """
    # given: 예전 포맷이 있는 저장 JSON (매개변수)
    stored = _stored(col("deal.name", format=legacy))

    # when: 저장 JSON을 읽는다
    column = definition_from_json(stored).columns[0]

    # then: 포맷과 앞 N자가 모두 None이다
    assert (column.format, column.prefix_length) == (None, None)


def test_legacy_prefix_becomes_prefix_option() -> None:
    """예전 앞 N자 포맷의 N은 앞 N자 옵션이 되고 포맷은 없어진다.

    테스트 코드: RQ-109
    """
    # given: prefix 포맷과 길이 7을 가진 저장 JSON
    stored = _stored(col("deal.name", format="prefix", prefix_length=7))

    # when: 저장 JSON을 읽는다
    column = definition_from_json(stored).columns[0]

    # then: 포맷은 None이고 앞 N자는 7이다
    assert (column.format, column.prefix_length) == (None, 7)


@pytest.mark.parametrize(
    "legacy", ["thousands", "krw_thousand", "krw_million", "decimal1", "percent_share"]
)
def test_legacy_number_formats_are_dropped_when_read(legacy: str) -> None:
    """예전 숫자 포맷은 읽을 때 포맷 없음이 되고 앞 N자는 그대로다.

    테스트 코드: RQ-110
    """
    # given: 예전 숫자 포맷과 앞 N자 3을 가진 금액 컬럼 JSON (매개변수)
    stored = _stored(col("deal.amount", format=legacy, prefix_length=3))

    # when: 저장 JSON을 읽는다
    column = definition_from_json(stored).columns[0]

    # then: 포맷은 None이고 앞 N자는 3이다
    assert (column.format, column.prefix_length) == (None, 3)


def test_current_formats_are_kept_when_read() -> None:
    """지금 포맷(ymd·quarter)은 읽어도 그대로다.

    테스트 코드: RQ-109
    """
    # given: 현재 포맷을 가진 저장 JSON
    stored = _stored(
        col("deal.expected_close", format="ymd"),
        col("deal.expected_close", format="quarter"),
        col("deal.amount"),
    )

    # when: 저장 JSON을 읽는다
    columns = definition_from_json(stored).columns

    # then: 포맷이 ymd, quarter, None 그대로다
    assert [c.format for c in columns] == ["ymd", "quarter", None]


def test_upgraded_definition_parses_and_writes_new_shape() -> None:
    """변환한 정의는 검증을 통과하고 다시 쓰면 예전 포맷 값이 남지 않는다.

    테스트 코드: RQ-109
    """
    # given: 예전 포맷이 섞인 저장 JSON
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415

    stored = _stored(
        col("deal.name", format="as_is"),
        col("deal.owner", format="name"),
        col("deal.status", format="key"),
        col("deal.code", format="prefix", prefix_length=4),
        col("deal.amount", format="percent_share"),
    )

    # when: 읽고 검증하고 다시 JSON으로 쓴다
    upgraded = definition_from_json(stored)
    parsed = parse_report_definition(upgraded)
    written: Any = definition_to_json(upgraded)

    # then: 앞 N자는 [None, None, None, 4, None]이고 쓴 JSON의 포맷은 모두 None이며 예전 값이 없다
    assert [c.prefix_length for c in parsed.columns] == [None, None, None, 4, None]
    assert [c["format"] for c in written["columns"]] == [None, None, None, None, None]
    assert written["columns"][3]["prefix_length"] == 4
    legacy = {"as_is", "prefix", "name", "key", "thousands", "krw_thousand", "krw_million"}
    assert not legacy & {c["format"] for c in written["columns"]}


# ---- 컬럼별 정렬 ----


def test_column_sort_round_trips_through_json() -> None:
    """컬럼 정렬은 JSON을 거쳐도 그대로다.

    테스트 코드: RQ-108
    """
    # given: 컬럼마다 정렬이 다른 정의
    definition = raw(
        [col("deal.name", sort="asc"), col("deal.vendor", sort="desc"), col("deal.code")]
    )

    # when: JSON을 거쳐 다시 읽는다
    reloaded = _through_json(definition)
    # then: 처음 정의와 같다
    assert reloaded == definition


def _with_top_sort(top: object, n: int = 3) -> dict[str, Any]:
    names = ["deal.code", "deal.name", "deal.vendor"][:n]
    stored = _stored(*[col(name) for name in names])
    stored["sort"] = top
    return stored


def test_legacy_top_level_sort_moves_to_that_column() -> None:
    """예전 최상위 정렬은 그 컬럼의 정렬로 옮겨진다.

    테스트 코드: RQ-111
    """
    # given: 컬럼 1을 내림차순으로 가리키는 최상위 정렬
    stored = _with_top_sort({"column": 1, "direction": "desc"})

    # when: 저장 JSON을 읽는다
    columns = definition_from_json(stored).columns

    # then: 컬럼 1만 desc다
    assert [c.sort for c in columns] == [None, "desc", None]


def test_legacy_sort_without_direction_is_ascending() -> None:
    """방향 없는 예전 정렬은 오름차순이 된다.

    테스트 코드: RQ-111
    """
    # when: 방향 없는 최상위 정렬(컬럼 0)을 읽는다
    columns = definition_from_json(_with_top_sort({"column": 0})).columns

    # then: 컬럼 0이 asc다
    assert [c.sort for c in columns] == ["asc", None, None]


def test_legacy_null_sort_means_no_sort() -> None:
    """예전 최상위 정렬이 null이면 정렬이 없다.

    테스트 코드: RQ-111
    """
    # when: 최상위 정렬 null인 JSON을 읽는다
    columns = definition_from_json(_with_top_sort(None)).columns

    # then: 모든 컬럼에 정렬이 없다
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
    """깨진 예전 최상위 정렬은 stored-invalid다.

    테스트 코드: RQ-112
    """
    # when·then: 깨진 최상위 정렬을 읽으면 ReportDefinitionError가 난다 (전제: 깨진 모양 매개변수)
    with pytest.raises(ReportDefinitionError) as caught:
        definition_from_json(_with_top_sort(broken))

    # then: 위반 하나가 stored-invalid다
    (issue,) = caught.value.issues
    assert issue.code == "stored-invalid"


def test_legacy_sort_with_unknown_direction_is_reported_when_run() -> None:
    """모르는 방향의 예전 정렬은 읽기는 되고 검증에서 sort-invalid다.

    테스트 코드: RQ-112
    """
    # given: 방향 "up"인 최상위 정렬 JSON
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415

    # when: 읽는다
    restored = definition_from_json(_with_top_sort({"column": 1, "direction": "up"}))

    # when·then: 읽은 정의를 검증하면 ReportDefinitionError가 난다
    with pytest.raises(ReportDefinitionError) as caught:
        parse_report_definition(restored)

    # then: 컬럼 1 sort 위치의 sort-invalid 하나다
    assert [(tuple(i.location), i.code) for i in caught.value.issues] == [
        (("columns", 1, "sort"), "sort-invalid")
    ]


def test_column_own_sort_wins_over_legacy_sort() -> None:
    """컬럼 자기 정렬은 예전 최상위 정렬보다 우선한다.

    테스트 코드: RQ-111
    """
    # given: 컬럼 1에 asc가 있고 최상위 정렬은 desc인 JSON
    stored = _stored(col("deal.code"), col("deal.name", sort="asc"))
    stored["sort"] = {"column": 1, "direction": "desc"}

    # when: 저장 JSON을 읽는다
    columns = definition_from_json(stored).columns

    # then: 컬럼 1은 asc 그대로다
    assert columns[1].sort == "asc"


def test_column_empty_sort_is_kept_over_legacy_sort() -> None:
    """컬럼의 빈 문자열 정렬도 예전 최상위 정렬보다 우선한다.

    테스트 코드: RQ-111
    """
    # given: 컬럼 1 정렬이 빈 문자열이고 최상위 정렬은 desc인 JSON
    stored = _stored(col("deal.code"), col("deal.name", sort=""))
    stored["sort"] = {"column": 1, "direction": "desc"}

    # when: 저장 JSON을 읽는다
    columns = definition_from_json(stored).columns

    # then: 컬럼 1은 빈 문자열 그대로다
    assert columns[1].sort == ""


def test_non_text_column_sort_is_stored_invalid() -> None:
    """문자열이 아닌 컬럼 정렬은 stored-invalid다.

    테스트 코드: RQ-112
    """
    # given: 컬럼 sort가 숫자 1인 JSON
    stored = _stored(col("deal.code", sort=1))

    # when·then: 읽으면 ReportDefinitionError가 난다
    with pytest.raises(ReportDefinitionError) as caught:
        definition_from_json(stored)

    # then: 위반 code가 stored-invalid다
    assert caught.value.issues[0].code == "stored-invalid"


def test_upgraded_legacy_sort_is_written_in_the_new_shape() -> None:
    """변환한 예전 정렬은 최상위 sort 없이 컬럼 sort로만 쓰인다.

    테스트 코드: RQ-111
    """
    # given: 컬럼 2를 내림차순으로 가리키는 최상위 정렬을 읽은 정의
    upgraded = definition_from_json(_with_top_sort({"column": 2, "direction": "desc"}))

    # when: 다시 JSON으로 쓴다
    written: Any = definition_to_json(upgraded)

    # then: 최상위 sort가 없고 컬럼 sort는 [None, None, "desc"]다
    assert "sort" not in written
    assert [c["sort"] for c in written["columns"]] == [None, None, "desc"]


def test_stored_json_without_combine_and_row_limit_reads_defaults() -> None:
    """결합과 행 수 제한 키가 없는 저장 JSON은 and·1000으로 읽힌다.

    테스트 코드: RQ-108
    """
    # given: combine·row_limit 키가 없는 저장 JSON
    stored = {"columns": [col("deal.code")]}
    # when: 저장 JSON을 읽는다
    restored = definition_from_json(stored)
    # then: 결합은 and, 행 수 제한은 1000이다
    assert (restored.combine, restored.row_limit) == ("and", 1000)
