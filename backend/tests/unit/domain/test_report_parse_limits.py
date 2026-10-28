"""리포트 정의 검증의 한도와 최상위 필드 (AC4, AC8): 컬럼·조건 수, 필드 key, 행 수,
컬럼별 정렬, 결합, 표시 이름, prefix 길이, 위반을 한꺼번에 보고하는 방식."""

import pytest

from app.domain.report.definition import ReportSort
from app.domain.report.errors import ReportDefinitionError
from app.domain.report.vocabulary import Combine, SortDirection
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


def test_column_sort_directions_become_sort_keys_in_column_order() -> None:
    definition = parse(
        [col("deal.name", sort="asc"), CODE, col("deal.vendor", sort="desc")],
    )

    assert definition.sort_keys() == (
        ReportSort(0, SortDirection.ASC),
        ReportSort(2, SortDirection.DESC),
    )
    assert definition.columns[1].sort is None


def test_definition_without_column_sort_has_no_sort_keys() -> None:
    assert parse([CODE, col("deal.name")]).sort_keys() == ()


@pytest.mark.parametrize("value", ["ASC", "up", ""])
def test_invalid_column_sort_is_reported_at_that_column(value: str) -> None:
    found = issues([col("deal.name", sort=value)])

    assert found == [(("columns", 0, "sort"), "sort-invalid")]


def test_every_invalid_column_sort_is_reported() -> None:
    found = issues(
        [col("deal.name", sort="up"), col("deal.vendor", sort="asc"), col("deal.code", sort="DESC")]
    )

    assert found == [
        (("columns", 0, "sort"), "sort-invalid"),
        (("columns", 2, "sort"), "sort-invalid"),
    ]


def test_group_and_aggregate_columns_can_be_sorted() -> None:
    definition = parse(
        [
            col("deal.status", group=True, sort="desc"),
            col("deal.amount", aggregate="sum", sort="asc"),
        ]
    )

    assert definition.sort_keys() == (
        ReportSort(0, SortDirection.DESC),
        ReportSort(1, SortDirection.ASC),
    )


def test_raw_definition_has_no_top_level_sort() -> None:
    from app.domain.report.raw import RawColumn, RawReportDefinition  # noqa: PLC0415

    assert "sort" not in RawReportDefinition.__dataclass_fields__
    assert RawColumn(field="deal.name", sort="asc").sort == "asc"


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


# ---- 포맷 없는 필드와 앞 N자 옵션 (2026-10-28) ----

LEGACY_FORMATS = ["as_is", "prefix", "name", "key"]
ANY_TYPE_FIELDS = [
    "deal.name",
    "deal.status",
    "deal.owner",
    "deal.amount",
    "deal.expected_close",
    "deal.created_at",
]


@pytest.mark.parametrize("field", ["deal.name", "deal.status", "deal.owner", "deal.amount"])
@pytest.mark.parametrize("legacy", LEGACY_FORMATS)
def test_legacy_format_is_rejected(field: str, legacy: str) -> None:
    found = issues([col(field, format=legacy)])

    assert found == [(("columns", 0, "format"), "format-not-allowed")]


def test_any_format_on_formatless_field_is_rejected_with_message() -> None:
    from app.domain.report.errors import ReportDefinitionError  # noqa: PLC0415
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415
    from tests.support.report_defs import raw  # noqa: PLC0415

    with pytest.raises(ReportDefinitionError) as caught:
        parse_report_definition(raw([col("deal.name", format="thousands")]))

    (issue,) = caught.value.issues
    assert (tuple(issue.location), issue.code) == (("columns", 0, "format"), "format-not-allowed")
    assert issue.message == "이 필드는 포맷을 고를 수 없습니다"


@pytest.mark.parametrize("field", ["deal.name", "deal.status", "deal.owner"])
def test_formatless_field_accepts_omitted_format(field: str) -> None:
    assert parse([col(field)]).columns[0].format is None


@pytest.mark.parametrize("field", ANY_TYPE_FIELDS)
@pytest.mark.parametrize("length", [1, 200])
def test_prefix_length_is_accepted_on_every_field_type(field: str, length: int) -> None:
    column = parse([col(field, prefix_length=length)]).columns[0]

    assert column.prefix_length == length


def test_prefix_length_on_group_and_aggregate_columns_is_accepted() -> None:
    columns = parse(
        [
            col("deal.vendor", group=True, prefix_length=3),
            col("deal.amount", aggregate="sum", prefix_length=5),
            col("action.count", prefix_length=2),
        ]
    ).columns

    assert [c.prefix_length for c in columns] == [3, 5, 2]


@pytest.mark.parametrize("length", [0, 201, -1, "20", 1.5, True])
def test_prefix_length_out_of_range_or_not_integer_is_rejected(length: object) -> None:
    from app.domain.report.errors import ReportDefinitionError  # noqa: PLC0415
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415
    from tests.support.report_defs import raw  # noqa: PLC0415

    with pytest.raises(ReportDefinitionError) as caught:
        parse_report_definition(raw([col("deal.name", prefix_length=length)]))

    (issue,) = caught.value.issues
    assert (tuple(issue.location), issue.code) == (
        ("columns", 0, "prefix_length"),
        "value-invalid",
    )
    assert issue.message == "앞 N자의 N은 1~200의 정수여야 합니다"


def test_omitted_prefix_length_is_none() -> None:
    assert parse([col("deal.name")]).columns[0].prefix_length is None
