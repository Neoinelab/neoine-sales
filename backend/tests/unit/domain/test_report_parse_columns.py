"""리포트 정의 검증의 컬럼 규칙.

포맷·집계 허용표, 그룹핑 규칙, 기본 집계, `action.count`의 특수 규칙을 본다.
"""

import pytest

from app.domain.report.vocabulary import Aggregate, Format
from tests.support.report_defs import col, cond, issues, parse

VENDOR_GROUP = col("deal.vendor", group=True)


def test_text_field_rejects_a_date_format() -> None:
    """텍스트 필드에 날짜 포맷을 주면 format-not-allowed다.

    테스트 코드: RQ-014
    """
    # when: 텍스트 필드에 분기 포맷을 준 정의를 검증한다
    found = issues([col("deal.code", format="quarter")])

    # then: 그 컬럼 format 위치의 format-not-allowed 하나다
    assert found == [(("columns", 0, "format"), "format-not-allowed")]


def test_number_field_rejects_quarter_format() -> None:
    """숫자 필드에 분기 포맷을 주면 format-not-allowed다.

    테스트 코드: RQ-014
    """
    # when: 금액에 분기 포맷을 준 정의를 검증한다
    found = issues([col("deal.amount", format="quarter")])

    # then: 그 컬럼 format 위치의 format-not-allowed 하나다
    assert found == [(("columns", 0, "format"), "format-not-allowed")]


@pytest.mark.parametrize(
    "legacy", ["thousands", "krw_thousand", "krw_million", "decimal1", "percent_share"]
)
def test_legacy_number_format_is_not_allowed(legacy: str) -> None:
    """예전 숫자 포맷은 format-not-allowed이고 문구는 포맷을 고를 수 없다는 안내다.

    테스트 코드: RQ-015
    """
    # given: 예전 숫자 포맷을 가진 요청 정의
    from app.domain.report.errors import ReportDefinitionError  # noqa: PLC0415
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415
    from tests.support.report_defs import raw  # noqa: PLC0415

    # when·then: 정의를 검증하면 ReportDefinitionError가 난다
    with pytest.raises(ReportDefinitionError) as caught:
        parse_report_definition(raw([col("deal.amount", format=legacy)]))

    # then: 위반은 format 위치의 format-not-allowed 하나이고 문구는 안내와 같다
    (issue,) = caught.value.issues
    assert (tuple(issue.location), issue.code) == (("columns", 0, "format"), "format-not-allowed")
    assert issue.message == "이 필드는 포맷을 고를 수 없습니다"


def test_date_field_rejects_ymd_hm_but_datetime_field_accepts_it() -> None:
    """시:분 포맷은 날짜 필드에서 거절되고 시각 필드에서 받아들여진다.

    테스트 코드: RQ-014
    """
    # when: 날짜 필드와 시각 필드에 ymd_hm을 준다
    date_issues = issues([col("deal.expected_close", format="ymd_hm")])
    time_format = parse([col("deal.created_at", format="ymd_hm")]).columns[0].format
    # then: 날짜 필드의 ymd_hm은 위반이고 시각 필드의 ymd_hm은 적용된다
    assert date_issues == [(("columns", 0, "format"), "format-not-allowed")]
    assert time_format == Format.YMD_HM


@pytest.mark.parametrize(
    "key",
    ["deal.last_updated_at", "deal.status_changed_at", "action.acted_at", "action.closed_at"],
)
def test_ymd_hm_on_the_four_date_converted_fields_is_format_not_allowed(key: str) -> None:
    """날짜로 바뀐 네 필드에 ymd_hm을 요청하면 format-not-allowed 위반이다.

    테스트 코드: RQ-114
    """
    # when: 네 필드에 ymd_hm을 주고 ymd는 허용되는지도 함께 검증한다
    rejected = issues([col(key, format="ymd_hm")])
    accepted = parse([col(key, format="ymd")]).columns[0].format
    # then: ymd_hm은 columns[0].format 위치의 format-not-allowed이고 ymd는 받아들여진다
    assert rejected == [(("columns", 0, "format"), "format-not-allowed")]
    assert accepted == Format.YMD


def test_omitted_format_is_none_for_non_date_and_default_for_date() -> None:
    """포맷을 생략하면 날짜 아닌 필드는 없음, 날짜는 ymd, 시각은 ymd_hm이다.

    테스트 코드: RQ-014
    """
    # when: 포맷 없이 여러 형식의 컬럼을 검증한다
    columns = parse(
        [
            col("deal.name"),
            col("deal.status"),
            col("deal.owner"),
            col("deal.amount"),
            col("deal.expected_close"),
            col("deal.created_at"),
        ]
    ).columns

    # then: 텍스트·코드·사용자·숫자는 None, 날짜는 ymd, 시각은 ymd_hm이다
    assert [c.format for c in columns] == [
        None,
        None,
        None,
        None,
        Format.YMD,
        Format.YMD_HM,
    ]


# ---- 그룹핑과 집계 ----


def test_grouped_report_requires_an_aggregate_for_a_non_number_column() -> None:
    """그룹핑 리포트에서 숫자가 아닌 컬럼은 집계가 없으면 aggregate-required다.

    테스트 코드: RQ-017
    """
    # when: 그룹 컬럼과 집계 없는 텍스트 컬럼을 검증한다
    found = issues([VENDOR_GROUP, col("deal.code")])

    # then: 그 컬럼 aggregate 위치의 aggregate-required 하나다
    assert found == [(("columns", 1, "aggregate"), "aggregate-required")]


def test_grouped_report_accepts_count_and_count_distinct_for_text() -> None:
    """텍스트 컬럼은 그룹핑할 때 건수·고유 건수를 받아들인다.

    테스트 코드: RQ-018
    """
    # when: 텍스트 컬럼에 건수와 고유 건수를 준 정의를 검증한다
    columns = parse(
        [
            VENDOR_GROUP,
            col("deal.code", aggregate="count"),
            col("deal.name", aggregate="count_distinct"),
        ]
    ).columns

    # then: 그룹 컬럼은 집계 없음, 나머지는 건수·고유 건수다
    assert [c.aggregate for c in columns] == [None, Aggregate.COUNT, Aggregate.COUNT_DISTINCT]


def test_grouped_report_applies_default_number_aggregates() -> None:
    """그룹핑할 때 금액은 합계, 체류 일수는 평균이 기본 집계다.

    테스트 코드: RQ-017
    """
    # when: 집계 없이 금액과 체류 일수를 그룹핑 리포트에 넣어 검증한다
    columns = parse([VENDOR_GROUP, col("deal.amount"), col("deal.status_days")]).columns

    # then: 금액은 합계, 체류 일수는 평균이다
    assert columns[1].aggregate == Aggregate.SUM
    assert columns[2].aggregate == Aggregate.AVG


def test_users_defaults_to_sum_when_grouped() -> None:
    """그룹핑할 때 Users count는 합계가 기본 집계다.

    테스트 코드: RQ-017
    """
    # when: 집계 없는 Users 컬럼을 검증한다
    aggregate = parse([VENDOR_GROUP, col("deal.users")]).columns[1].aggregate
    # then: 집계는 합계다
    assert aggregate == Aggregate.SUM


@pytest.mark.parametrize("aggregate", ["sum", "avg", "min", "max"])
def test_number_column_accepts_the_four_numeric_aggregates(aggregate: str) -> None:
    """숫자 컬럼은 합계·평균·최소·최대를 받아들인다.

    테스트 코드: RQ-018
    """
    # when: 숫자 컬럼에 집계 하나를 주고 검증한다 (전제: 집계 4개 매개변수)
    columns = parse([VENDOR_GROUP, col("deal.amount", aggregate=aggregate)]).columns

    # then: 준 집계가 그대로 적용된다
    assert columns[1].aggregate == Aggregate(aggregate)


def test_number_column_rejects_count() -> None:
    """숫자 컬럼에 건수 집계를 주면 aggregate-not-allowed다.

    테스트 코드: RQ-018
    """
    # when: 금액에 건수 집계를 준 정의를 검증한다
    found = issues([VENDOR_GROUP, col("deal.amount", aggregate="count")])

    # then: 그 컬럼 aggregate 위치의 aggregate-not-allowed 하나다
    assert found == [(("columns", 1, "aggregate"), "aggregate-not-allowed")]


def test_text_column_rejects_sum_when_grouped() -> None:
    """텍스트 컬럼에 합계 집계를 주면 aggregate-not-allowed다.

    테스트 코드: RQ-018
    """
    # when: 텍스트 컬럼에 합계 집계를 준 정의를 검증한다
    found = issues([VENDOR_GROUP, col("deal.name", aggregate="sum")])

    # then: 그 컬럼 aggregate 위치의 aggregate-not-allowed 하나다
    assert found == [(("columns", 1, "aggregate"), "aggregate-not-allowed")]


def test_unknown_aggregate_name_is_rejected() -> None:
    """모르는 집계 이름은 aggregate-not-allowed다.

    테스트 코드: RQ-018
    """
    # when: 집계 이름 median을 준 정의를 검증한다
    found = issues([VENDOR_GROUP, col("deal.amount", aggregate="median")])

    # then: 그 컬럼 aggregate 위치의 aggregate-not-allowed 하나다
    assert found == [(("columns", 1, "aggregate"), "aggregate-not-allowed")]


def test_aggregate_without_any_grouping_is_rejected() -> None:
    """그룹핑이 없는데 집계를 주면 aggregate-not-allowed다.

    테스트 코드: RQ-019
    """
    # when: 그룹 컬럼이 없는 정의에 집계를 준다
    found = issues([col("deal.code", aggregate="count")])

    # then: 그 컬럼 aggregate 위치의 aggregate-not-allowed 하나다
    assert found == [(("columns", 0, "aggregate"), "aggregate-not-allowed")]


def test_group_column_with_aggregate_is_rejected() -> None:
    """그룹 컬럼에 집계를 주면 aggregate-not-allowed다.

    테스트 코드: RQ-019
    """
    # when: 그룹 컬럼에 건수 집계를 준 정의를 검증한다
    found = issues([col("deal.vendor", group=True, aggregate="count")])

    # then: 그 컬럼 aggregate 위치의 aggregate-not-allowed 하나다
    assert found == [(("columns", 0, "aggregate"), "aggregate-not-allowed")]


def test_ungrouped_report_leaves_aggregates_empty() -> None:
    """그룹핑이 없는 리포트는 집계가 모두 비고 그룹 표시도 없다.

    테스트 코드: RQ-019
    """
    # when: 그룹 없이 금액·Deal code 컬럼을 검증한다
    columns = parse([col("deal.amount"), col("deal.code")]).columns

    # then: 집계는 모두 None이고 그룹 표시는 모두 False다
    assert [c.aggregate for c in columns] == [None, None]
    assert [c.group for c in columns] == [False, False]


def test_a_date_column_can_be_grouped_by_quarter() -> None:
    """날짜 컬럼은 분기 포맷으로 그룹핑할 수 있다.

    테스트 코드: RQ-014
    """
    # when: 분기 포맷의 날짜 그룹 컬럼을 검증한다
    columns = parse([col("deal.expected_close", format="quarter", group=True)]).columns

    # then: 그룹이고 포맷은 분기다
    assert columns[0].group is True
    assert columns[0].format == Format.QUARTER


# ---- action.count ----


def test_action_count_without_grouping_is_rejected() -> None:
    """그룹핑 없이 Action 건수를 쓰면 grouping-required다.

    테스트 코드: RQ-020
    """
    # when: 그룹핑 없이 action.count를 검증한다
    found = issues([col("action.count")])
    # then: 컬럼 위치의 grouping-required 하나다
    assert found == [(("columns", 0), "grouping-required")]


def test_action_count_in_conditions_is_not_filterable() -> None:
    """Action 건수를 조건에 쓰면 not-filterable이다.

    테스트 코드: RQ-020
    """
    # when: Action 건수 필드로 조건을 준 정의를 검증한다
    found = issues([VENDOR_GROUP, col("action.count")], [cond("action.count", "eq", 1)])

    # then: 조건 field 위치의 not-filterable 하나다
    assert found == [(("conditions", 0, "field"), "not-filterable")]


def test_action_count_cannot_be_a_group_column() -> None:
    """Action 건수를 그룹 컬럼으로 쓰면 group-not-allowed다.

    테스트 코드: RQ-020
    """
    # when: Action 건수를 그룹 컬럼으로 준 정의를 검증한다
    found = issues([VENDOR_GROUP, col("action.count", group=True)])

    # then: 그 컬럼 group 위치의 group-not-allowed 하나다
    assert found == [(("columns", 1, "group"), "group-not-allowed")]


def test_action_count_accepts_only_count_as_aggregate() -> None:
    """Action 건수에 건수 아닌 집계를 주면 aggregate-not-allowed다.

    테스트 코드: RQ-020
    """
    # when: Action 건수에 합계 집계를 준 정의를 검증한다
    found = issues([VENDOR_GROUP, col("action.count", aggregate="sum")])

    # then: 그 컬럼 aggregate 위치의 aggregate-not-allowed 하나다
    assert found == [(("columns", 1, "aggregate"), "aggregate-not-allowed")]


def test_action_count_is_accepted_when_grouped_with_or_without_count() -> None:
    """그룹핑할 때 Action 건수는 집계 생략·건수 모두 건수 집계로 받아들여진다.

    테스트 코드: RQ-020
    """
    # when: Action 건수를 집계 생략과 건수 지정으로 각각 검증한다
    plain = parse([VENDOR_GROUP, col("action.count")]).columns[1]
    explicit = parse([VENDOR_GROUP, col("action.count", aggregate="count")]).columns[1]

    # then: 둘 다 집계가 건수다
    assert plain.aggregate == Aggregate.COUNT
    assert explicit.aggregate == Aggregate.COUNT
