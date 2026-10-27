"""리포트 정의 검증의 한도와 최상위 필드 (AC4, AC8): 컬럼·조건 수, 필드 key, 행 수, 정렬, 결합,
표시 이름, prefix 길이, 위반을 한꺼번에 보고하는 방식."""

import pytest

from app.domain.report.errors import ReportDefinitionError
from app.domain.report.vocabulary import Combine, Format, SortDirection
from tests.support.report_defs import col, cond, issues, parse

CODE = col("deal.code")


def test_unknown_field_is_reported_with_its_location() -> None:
    found = issues([CODE, col("deal.password")])

    assert found == [(("columns", 1, "field"), "unknown-field")]


def test_unknown_condition_field_is_reported_and_later_checks_are_skipped() -> None:
    found = issues([CODE], [cond("deal.password", "gt", "x")])

    assert found == [(("conditions", 0, "field"), "unknown-field")]


@pytest.mark.parametrize(
    "key", ["Deal.Code", "deal.code ", "DEAL.CODE", "deal", "", "deal.code;--"]
)
def test_field_keys_must_match_the_catalog_exactly(key: str) -> None:
    assert issues([col(key)]) == [(("columns", 0, "field"), "unknown-field")]


def test_unknown_field_message_names_the_field_in_korean() -> None:
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415
    from tests.support.report_defs import raw  # noqa: PLC0415 - 지연 import

    with pytest.raises(ReportDefinitionError) as caught:
        parse_report_definition(raw([col("deal.password")]))

    assert "deal.password" in caught.value.issues[0].message
    assert str(caught.value) == caught.value.issues[0].message


@pytest.mark.parametrize("count", [0, 31])
def test_column_count_outside_one_to_thirty_is_rejected(count: int) -> None:
    columns = [CODE] * count

    assert issues(columns) == [(("columns",), "columns-count")]


@pytest.mark.parametrize("count", [1, 30])
def test_column_count_at_the_boundaries_is_accepted(count: int) -> None:
    assert len(parse([CODE] * count).columns) == count


def test_twenty_one_conditions_are_rejected() -> None:
    found = issues([CODE], [cond("deal.name", "contains", "a")] * 21)

    assert found == [(("conditions",), "conditions-count")]


def test_twenty_conditions_and_none_are_accepted() -> None:
    assert len(parse([CODE], [cond("deal.name", "contains", "a")] * 20).conditions) == 20
    assert parse([CODE]).conditions == ()


@pytest.mark.parametrize("limit", [100, 1000, 10000])
def test_the_three_row_limits_are_accepted(limit: int) -> None:
    assert parse([CODE], row_limit=limit).row_limit == limit


@pytest.mark.parametrize("limit", [0, 99, 101, 999, 10001, -1, True, "1000", None, 1000.0])
def test_row_limit_outside_the_three_choices_is_rejected(limit: object) -> None:
    assert issues([CODE], row_limit=limit) == [(("row_limit",), "row-limit-invalid")]


def test_combine_accepts_and_or_only() -> None:
    assert parse([CODE], combine="and").combine == Combine.AND
    assert parse([CODE], combine="or").combine == Combine.OR
    assert issues([CODE], combine="xor") == [(("combine",), "combine-invalid")]


def test_sort_points_to_a_column_and_defaults_ascending() -> None:
    definition = parse([CODE, col("deal.name")], sort={"column": 1, "direction": "desc"})

    assert definition.sort is not None
    assert definition.sort.column == 1
    assert definition.sort.direction == SortDirection.DESC
    assert parse([CODE]).sort is None


@pytest.mark.parametrize("position", [-1, 2, 99, "0", True])
def test_sort_column_outside_the_columns_is_rejected(position: object) -> None:
    found = issues([CODE, col("deal.name")], sort={"column": position, "direction": "asc"})

    assert found == [(("sort", "column"), "sort-invalid")]


def test_sort_direction_other_than_asc_desc_is_rejected() -> None:
    found = issues([CODE], sort={"column": 0, "direction": "up"})

    assert found == [(("sort", "direction"), "sort-invalid")]


def test_all_violations_are_reported_together() -> None:
    found = issues(
        [col("deal.password"), col("deal.code", format="quarter")],
        [cond("deal.name", "gt", "x")],
        combine="xor",
    )

    assert set(found) == {
        (("columns", 0, "field"), "unknown-field"),
        (("columns", 1, "format"), "format-not-allowed"),
        (("conditions", 0, "operator"), "operator-not-allowed"),
        (("combine",), "combine-invalid"),
    }
    assert [loc for loc, _ in found if loc[0] == "columns"] == [
        ("columns", 0, "field"),
        ("columns", 1, "format"),
    ]


def test_every_issue_has_a_korean_message() -> None:
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415
    from tests.support.report_defs import raw  # noqa: PLC0415

    with pytest.raises(ReportDefinitionError) as caught:
        parse_report_definition(raw([col("deal.password"), col("deal.code", format="quarter")]))

    messages = [i.message for i in caught.value.issues]
    assert len(messages) == 2
    assert all(any("가" <= ch <= "힣" for ch in m) for m in messages)


# ---- 표시 이름 ----


def test_label_is_trimmed_and_defaults_to_the_field_label() -> None:
    columns = parse([col("deal.code", label="  건수  "), col("deal.name")]).columns

    assert columns[0].label == "건수"
    assert columns[1].label == "Deal 이름"


def test_label_of_exactly_one_hundred_characters_is_accepted() -> None:
    assert parse([col("deal.code", label="가" * 100)]).columns[0].label == "가" * 100


@pytest.mark.parametrize("label", ["   ", "", "가" * 101, "a\x00b"])
def test_blank_overlong_or_nul_label_is_rejected(label: str) -> None:
    assert issues([col("deal.code", label=label)]) == [(("columns", 0, "label"), "label-invalid")]


# ---- prefix 길이 ----


@pytest.mark.parametrize("length", [1, 200])
def test_prefix_format_accepts_length_one_to_two_hundred(length: int) -> None:
    column = parse([col("deal.name", format="prefix", prefix_length=length)]).columns[0]

    assert column.format == Format.PREFIX
    assert column.prefix_length == length


@pytest.mark.parametrize("length", [0, 201, -1, None, True, "5"])
def test_prefix_format_rejects_missing_or_out_of_range_length(length: object) -> None:
    found = issues([col("deal.name", format="prefix", prefix_length=length)])

    assert found == [(("columns", 0, "prefix_length"), "value-invalid")]


def test_prefix_length_on_another_format_is_rejected() -> None:
    found = issues([col("deal.name", format="as_is", prefix_length=5)])

    assert found == [(("columns", 0, "prefix_length"), "value-invalid")]
