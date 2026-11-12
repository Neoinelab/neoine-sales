"""리포트 정의 검증의 한도와 최상위 필드.

컬럼·조건 수, 필드 key, 행 수, 컬럼별 정렬, 결합, 표시 이름, 앞 N자,
위반을 한꺼번에 보고하는 방식을 본다.
"""

import pytest

from app.domain.report.definition import ReportSort
from app.domain.report.errors import ReportDefinitionError
from app.domain.report.vocabulary import Combine, SortDirection
from tests.support.report_defs import col, cond, issues, parse

CODE = col("deal.code")


def test_unknown_field_is_reported_with_its_location() -> None:
    """모르는 필드는 그 컬럼의 field 위치로 알린다.

    테스트 코드: RQ-011
    """
    # when: 카탈로그에 없는 필드를 가진 정의를 검증한다
    found = issues([CODE, col("deal.password")])

    # then: 그 컬럼 field 위치의 unknown-field 하나다
    assert found == [(("columns", 1, "field"), "unknown-field")]


def test_unknown_condition_field_is_reported_and_later_checks_are_skipped() -> None:
    """모르는 조건 필드는 field 위치로 알리고 연산자·값 검사는 건너뛴다.

    테스트 코드: RQ-011
    """
    # when: 모르는 필드의 조건이 있는 정의를 검증한다
    found = issues([CODE], [cond("deal.password", "gt", "x")])

    # then: 조건 field 위치의 unknown-field 하나뿐이다
    assert found == [(("conditions", 0, "field"), "unknown-field")]


@pytest.mark.parametrize(
    "key", ["Deal.Code", "deal.code ", "DEAL.CODE", "deal", "", "deal.code;--"]
)
def test_field_keys_must_match_the_catalog_exactly(key: str) -> None:
    """필드 key는 대소문자·공백까지 카탈로그와 정확히 같아야 한다.

    테스트 코드: RQ-011
    """
    # when: 변형한 key로 컬럼을 검증한다 (전제: key 변형 매개변수)
    found = issues([col(key)])
    # then: unknown-field다
    assert found == [(("columns", 0, "field"), "unknown-field")]


def test_unknown_field_message_names_the_field_in_korean() -> None:
    """모르는 필드 위반 문구는 한국어이고 필드 key를 담는다.

    테스트 코드: RQ-011
    """
    # given: 카탈로그에 없는 필드를 가진 요청 정의
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415
    from tests.support.report_defs import raw  # noqa: PLC0415 - 지연 import

    # when·then: 정의를 검증하면 ReportDefinitionError가 난다
    with pytest.raises(ReportDefinitionError) as caught:
        parse_report_definition(raw([col("deal.password")]))

    # then: 첫 위반 문구에 key가 있고 오류 문자열은 그 문구다
    assert "deal.password" in caught.value.issues[0].message
    assert str(caught.value) == caught.value.issues[0].message


@pytest.mark.parametrize("count", [0, 31])
def test_column_count_outside_one_to_thirty_is_rejected(count: int) -> None:
    """컬럼이 0개이거나 31개이면 columns-count다.

    테스트 코드: RQ-012
    """
    # given: 컬럼 수가 범위 밖인 정의 (매개변수)
    columns = [CODE] * count

    # when: 정의를 검증한다
    found = issues(columns)
    # then: columns 위치의 columns-count 하나다
    assert found == [(("columns",), "columns-count")]


@pytest.mark.parametrize("count", [1, 30])
def test_column_count_at_the_boundaries_is_accepted(count: int) -> None:
    """컬럼 1개와 30개는 허용된다.

    테스트 코드: RQ-012
    """
    # when: 경계 개수의 정의를 검증한다
    column_count = len(parse([CODE] * count).columns)
    # then: 컬럼 수가 그대로다
    assert column_count == count


def test_twenty_one_conditions_are_rejected() -> None:
    """조건이 21개이면 conditions-count다.

    테스트 코드: RQ-022
    """
    # when: 조건 21개짜리 정의를 검증한다
    found = issues([CODE], [cond("deal.name", "contains", "a")] * 21)

    # then: conditions 위치의 conditions-count 하나다
    assert found == [(("conditions",), "conditions-count")]


def test_twenty_conditions_and_none_are_accepted() -> None:
    """조건 20개와 0개는 허용된다.

    테스트 코드: RQ-022
    """
    # when: 조건 20개의 정의와 조건 없는 정의를 검증한다
    twenty = parse([CODE], [cond("deal.name", "contains", "a")] * 20).conditions
    none = parse([CODE]).conditions
    # then: 20개는 받아들여지고 조건 없음은 빈 목록이다
    assert len(twenty) == 20
    assert none == ()


@pytest.mark.parametrize("limit", [100, 1000, 10000])
def test_the_three_row_limits_are_accepted(limit: int) -> None:
    """행 수 제한 100·1000·10000은 허용된다.

    테스트 코드: RQ-027
    """
    # when: 행 수 제한을 준 정의를 검증한다 (전제: 3개 값 매개변수)
    applied = parse([CODE], row_limit=limit).row_limit
    # then: 준 값 그대로다
    assert applied == limit


@pytest.mark.parametrize("limit", [0, 99, 101, 999, 10001, -1, True, "1000", None, 1000.0])
def test_row_limit_outside_the_three_choices_is_rejected(limit: object) -> None:
    """행 수 제한이 세 값이 아니면 row-limit-invalid다.

    테스트 코드: RQ-027
    """
    # when: 틀린 행 수 제한을 검증한다 (전제: 틀린 값 매개변수)
    found = issues([CODE], row_limit=limit)
    # then: row_limit 위치의 row-limit-invalid 하나다
    assert found == [(("row_limit",), "row-limit-invalid")]


def test_combine_accepts_and_or_only() -> None:
    """결합은 and·or만 받고 다른 값은 combine-invalid다.

    테스트 코드: RQ-027
    """
    # when: and·or·xor를 각각 검증한다
    and_combine = parse([CODE], combine="and").combine
    or_combine = parse([CODE], combine="or").combine
    xor_issues = issues([CODE], combine="xor")
    # then: and·or는 적용되고 xor는 combine 위치의 combine-invalid다
    assert and_combine == Combine.AND
    assert or_combine == Combine.OR
    assert xor_issues == [(("combine",), "combine-invalid")]


def test_column_sort_directions_become_sort_keys_in_column_order() -> None:
    """컬럼 정렬은 컬럼 순서대로 정렬 키가 된다.

    테스트 코드: RQ-021
    """
    # given: 첫째·셋째 컬럼에만 정렬을 준 정의
    definition = parse(
        [col("deal.name", sort="asc"), CODE, col("deal.vendor", sort="desc")],
    )

    # when: 정렬 키를 구한다
    sort_keys = definition.sort_keys()
    # then: 컬럼 index 순서의 둘이다
    assert sort_keys == (
        ReportSort(0, SortDirection.ASC),
        ReportSort(2, SortDirection.DESC),
    )
    # then: 정렬을 안 준 컬럼은 정렬이 없다
    assert definition.columns[1].sort is None


def test_definition_without_column_sort_has_no_sort_keys() -> None:
    """컬럼 정렬이 없으면 정렬 키가 없다.

    테스트 코드: RQ-021
    """
    # when: 정렬을 주지 않은 정의의 정렬 키를 구한다
    sort_keys = parse([CODE, col("deal.name")]).sort_keys()
    # then: 빈 튜플이다
    assert sort_keys == ()


@pytest.mark.parametrize("value", ["ASC", "up", ""])
def test_invalid_column_sort_is_reported_at_that_column(value: str) -> None:
    """틀린 정렬 값은 그 컬럼의 sort 위치로 sort-invalid다.

    테스트 코드: RQ-021
    """
    # when: 틀린 정렬 값을 준 정의를 검증한다 (전제: 값 매개변수)
    found = issues([col("deal.name", sort=value)])

    # then: 그 컬럼 sort 위치의 sort-invalid 하나다
    assert found == [(("columns", 0, "sort"), "sort-invalid")]


def test_every_invalid_column_sort_is_reported() -> None:
    """틀린 정렬 값은 컬럼마다 하나씩 모두 알린다.

    테스트 코드: RQ-021
    """
    # when: 정렬이 틀린 컬럼이 둘인 정의를 검증한다
    found = issues(
        [col("deal.name", sort="up"), col("deal.vendor", sort="asc"), col("deal.code", sort="DESC")]
    )

    # then: 첫째·셋째 컬럼 위치의 sort-invalid 둘이다
    assert found == [
        (("columns", 0, "sort"), "sort-invalid"),
        (("columns", 2, "sort"), "sort-invalid"),
    ]


def test_group_and_aggregate_columns_can_be_sorted() -> None:
    """그룹 컬럼과 집계 컬럼도 정렬할 수 있다.

    테스트 코드: RQ-021
    """
    # given: 그룹 컬럼과 집계 컬럼에 정렬을 준 정의
    definition = parse(
        [
            col("deal.status", group=True, sort="desc"),
            col("deal.amount", aggregate="sum", sort="asc"),
        ]
    )

    # when: 정렬 키를 구한다
    sort_keys = definition.sort_keys()
    # then: 둘이 컬럼 순서다
    assert sort_keys == (
        ReportSort(0, SortDirection.DESC),
        ReportSort(1, SortDirection.ASC),
    )


def test_raw_definition_has_no_top_level_sort() -> None:
    """원시 정의에는 최상위 정렬이 없고 정렬은 컬럼에만 있다.

    테스트 코드: RQ-009
    """
    # when: 원시 정의 모양을 본다
    from app.domain.report.raw import RawColumn, RawReportDefinition  # noqa: PLC0415

    # then: 최상위 sort 필드가 없고 원시 컬럼에는 sort가 있다
    assert "sort" not in RawReportDefinition.__dataclass_fields__
    assert RawColumn(field="deal.name", sort="asc").sort == "asc"


def test_all_violations_are_reported_together() -> None:
    """여러 위반은 처음에 멈추지 않고 컬럼 → 조건 → 결합 순서로 모두 알린다.

    테스트 코드: RQ-010
    """
    # when: 컬럼·조건·결합이 모두 틀린 정의를 검증한다
    found = issues(
        [col("deal.password"), col("deal.code", format="quarter")],
        [cond("deal.name", "gt", "x")],
        combine="xor",
    )

    # then: 네 위반이 모두 있고 컬럼 위반은 index 순이다
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
    """모든 위반 문구는 한국어다.

    테스트 코드: RQ-010
    """
    # given: 위반이 두 개인 요청 정의
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415
    from tests.support.report_defs import raw  # noqa: PLC0415

    # when·then: 정의를 검증하면 ReportDefinitionError가 난다
    with pytest.raises(ReportDefinitionError) as caught:
        parse_report_definition(raw([col("deal.password"), col("deal.code", format="quarter")]))

    # then: 위반 문구 둘 다 한글을 포함한다
    messages = [i.message for i in caught.value.issues]
    assert len(messages) == 2
    assert all(any("가" <= ch <= "힣" for ch in m) for m in messages)


# ---- 표시 이름 ----


def test_label_is_trimmed_and_defaults_to_the_field_label() -> None:
    """표시 이름은 앞뒤 공백을 지우고 생략하면 필드 이름이다.

    테스트 코드: RQ-013
    """
    # when: 공백이 있는 표시 이름과 표시 이름 없는 컬럼을 검증한다
    columns = parse([col("deal.code", label="  건수  "), col("deal.name")]).columns

    # then: 다듬은 이름과 필드 이름이다
    assert columns[0].label == "건수"
    assert columns[1].label == "Deal 이름"


def test_label_of_exactly_one_hundred_characters_is_accepted() -> None:
    """표시 이름 정확히 100자는 허용된다.

    테스트 코드: RQ-013
    """
    # when: 100자 표시 이름의 정의를 검증한다
    label = parse([col("deal.code", label="가" * 100)]).columns[0].label
    # then: 그대로 적용된다
    assert label == "가" * 100


@pytest.mark.parametrize("label", ["   ", "", "가" * 101, "a\x00b"])
def test_blank_overlong_or_nul_label_is_rejected(label: str) -> None:
    """빈 값·공백뿐·101자·NUL 포함 표시 이름은 label-invalid다.

    테스트 코드: RQ-013
    """
    # when: 틀린 표시 이름을 검증한다 (전제: 값 매개변수)
    found = issues([col("deal.code", label=label)])
    # then: 그 컬럼 label 위치의 label-invalid 하나다
    assert found == [(("columns", 0, "label"), "label-invalid")]


# ---- 포맷 없는 필드와 앞 N자 옵션 ----

LEGACY_FORMATS = [
    "as_is",
    "prefix",
    "name",
    "key",
    "thousands",
    "krw_thousand",
    "krw_million",
    "decimal1",
    "percent_share",
]
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
    """예전 포맷은 포맷 없는 필드에서 format-not-allowed다.

    테스트 코드: RQ-015
    """
    # when: 예전 포맷 이름을 준 정의를 검증한다 (전제: 필드·포맷 매개변수)
    found = issues([col(field, format=legacy)])

    # then: 그 컬럼 format 위치의 format-not-allowed 하나다
    assert found == [(("columns", 0, "format"), "format-not-allowed")]


def test_any_format_on_formatless_field_is_rejected_with_message() -> None:
    """포맷 없는 필드에 포맷을 주면 위반 문구가 안내와 같다.

    테스트 코드: RQ-014
    """
    # given: 포맷 없는 필드에 포맷을 준 요청 정의
    from app.domain.report.errors import ReportDefinitionError  # noqa: PLC0415
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415
    from tests.support.report_defs import raw  # noqa: PLC0415

    # when·then: 정의를 검증하면 ReportDefinitionError가 난다
    with pytest.raises(ReportDefinitionError) as caught:
        parse_report_definition(raw([col("deal.name", format="thousands")]))

    # then: format-not-allowed 위반 하나와 고정 문구다
    (issue,) = caught.value.issues
    assert (tuple(issue.location), issue.code) == (("columns", 0, "format"), "format-not-allowed")
    assert issue.message == "이 필드는 포맷을 고를 수 없습니다"


@pytest.mark.parametrize("field", ["deal.name", "deal.status", "deal.owner"])
def test_formatless_field_accepts_omitted_format(field: str) -> None:
    """포맷 없는 필드는 포맷을 생략하면 포맷이 없다.

    테스트 코드: RQ-014
    """
    # when: 필드의 포맷 없는 컬럼을 검증한다 (전제: 필드 매개변수)
    applied = parse([col(field)]).columns[0].format
    # then: 적용된 포맷이 None이다
    assert applied is None


@pytest.mark.parametrize("field", ANY_TYPE_FIELDS)
@pytest.mark.parametrize("length", [1, 200])
def test_prefix_length_is_accepted_on_every_field_type(field: str, length: int) -> None:
    """앞 N자는 모든 필드 형식에서 1과 200을 받아들인다.

    테스트 코드: RQ-016
    """
    # when: 앞 N자를 준 컬럼을 검증한다 (전제: 필드·길이 매개변수)
    column = parse([col(field, prefix_length=length)]).columns[0]

    # then: 준 길이가 그대로 적용된다
    assert column.prefix_length == length


def test_prefix_length_on_group_and_aggregate_columns_is_accepted() -> None:
    """앞 N자는 그룹·집계 컬럼에도 쓸 수 있다.

    테스트 코드: RQ-016
    """
    # when: 그룹·집계·Action 건수 컬럼에 앞 N자를 준 정의를 검증한다
    columns = parse(
        [
            col("deal.vendor", group=True, prefix_length=3),
            col("deal.amount", aggregate="sum", prefix_length=5),
            col("action.count", prefix_length=2),
        ]
    ).columns

    # then: 길이가 컬럼마다 그대로다
    assert [c.prefix_length for c in columns] == [3, 5, 2]


@pytest.mark.parametrize("length", [0, 201, -1, "20", 1.5, True])
def test_prefix_length_out_of_range_or_not_integer_is_rejected(length: object) -> None:
    """앞 N자가 범위 밖이거나 정수가 아니면 value-invalid이고 문구가 안내와 같다.

    테스트 코드: RQ-016
    """
    # given: 잘못된 앞 N자를 가진 요청 정의 (매개변수)
    from app.domain.report.errors import ReportDefinitionError  # noqa: PLC0415
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415
    from tests.support.report_defs import raw  # noqa: PLC0415

    # when·then: 정의를 검증하면 ReportDefinitionError가 난다
    with pytest.raises(ReportDefinitionError) as caught:
        parse_report_definition(raw([col("deal.name", prefix_length=length)]))

    # then: prefix_length 위치의 value-invalid 하나와 고정 문구다
    (issue,) = caught.value.issues
    assert (tuple(issue.location), issue.code) == (
        ("columns", 0, "prefix_length"),
        "value-invalid",
    )
    assert issue.message == "앞 N자의 N은 1~200의 정수여야 합니다"


def test_omitted_prefix_length_is_none() -> None:
    """앞 N자를 생략하면 None이다.

    테스트 코드: RQ-016
    """
    # when: 앞 N자 없는 컬럼을 검증한다
    applied = parse([col("deal.name")]).columns[0].prefix_length
    # then: 적용된 앞 N자가 None이다
    assert applied is None
