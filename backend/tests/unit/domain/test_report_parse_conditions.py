"""리포트 정의 검증의 조건 규칙: 형식별 연산자, 연산자별 값 모양, 해석된 값 객체."""

import pytest

from app.domain.report.condition_values import (
    DateRange,
    DateValue,
    IdList,
    KeyList,
    NoValue,
    NumberRange,
    NumberValue,
    RelativeValue,
    TextValue,
)
from app.domain.report.vocabulary import Operator, RelativePeriod
from tests.support.report_defs import VALID_CONDITIONS as VALID
from tests.support.report_defs import col, cond, issues, parse

CODE = col("deal.code")


def _only_condition_issue(field: str, operator: str, value: object) -> list[tuple[object, str]]:
    return issues([CODE], [cond(field, operator, value)])  # type: ignore[return-value]


@pytest.mark.parametrize(
    ("field", "operator"),
    [
        ("deal.name", "gt"),
        ("deal.name", "in"),
        ("deal.vendor", "contains"),
        ("deal.vendor", "eq"),
        ("deal.owner", "between"),
        ("deal.amount", "contains"),
        ("deal.amount", "in"),
        ("deal.expected_close", "eq"),
        ("deal.expected_close", "is_empty"),
        ("deal.created_at", "gte"),
        ("deal.status", "is_not_empty"),
        ("deal.nothing", "eq"),
    ],
)
def test_operator_not_allowed_for_type_is_rejected(field: str, operator: str) -> None:
    """형식에 맞지 않는 연산자는 operator-not-allowed이고 없는 필드는 unknown-field다.

    테스트 코드: RQ-023
    """
    # given: 필드·연산자 조합(매개변수)
    code = "unknown-field" if field == "deal.nothing" else "operator-not-allowed"
    location = "field" if field == "deal.nothing" else "operator"

    # when: 조건 하나를 검증한다
    found = _only_condition_issue(field, operator, "x")
    # then: 해당 위치의 위반 하나뿐이다
    assert found == [(("conditions", 0, location), code)]


@pytest.mark.parametrize(("field", "operator", "value"), VALID)
def test_valid_condition_shapes_are_accepted(field: str, operator: str, value: object) -> None:
    """형식에 맞는 연산자·값 조합은 받아들여진다.

    테스트 코드: RQ-024
    """
    # when: 올바른 조건 하나를 검증한다 (전제: 조합 매개변수)
    definition = parse([CODE], [cond(field, operator, value)])

    # then: 조건의 필드와 연산자가 그대로 정의에 들어간다
    assert definition.conditions[0].field.key == field
    assert definition.conditions[0].operator == Operator(operator)


INVALID = [
    ("deal.vendor", "in", []),
    ("deal.vendor", "in", list(range(1, 102))),
    ("deal.vendor", "in", ["a"]),
    ("deal.vendor", "in", [True]),
    ("deal.vendor", "in", 5),
    ("deal.vendor", "is_empty", [1]),
    ("deal.status", "in", [1]),
    ("deal.status", "in", []),
    ("deal.amount", "between", [10, 5]),
    ("deal.amount", "between", [1]),
    ("deal.amount", "between", [1, 2, 3]),
    ("deal.amount", "eq", True),
    ("deal.amount", "eq", 1.5),
    ("deal.amount", "eq", "10"),
    ("deal.amount", "eq", None),
    ("deal.amount", "gt", 2**53),
    ("deal.expected_close", "before", "2026-13-01"),
    ("deal.expected_close", "before", "2026/01/01"),
    ("deal.expected_close", "before", 20260101),
    ("deal.expected_close", "between", ["2026-02-01", "2026-01-01"]),
    ("deal.expected_close", "between", ["2026-01-01"]),
    ("deal.name", "contains", "   "),
    ("deal.name", "contains", "x" * 201),
    ("deal.name", "contains", "a\x00b"),
    ("deal.name", "contains", 5),
    ("deal.name", "is_empty", "x"),
    ("deal.expected_close", "relative", {"period": "last_n_days", "days": 0}),
    ("deal.expected_close", "relative", {"period": "last_n_days", "days": 3651}),
    ("deal.expected_close", "relative", {"period": "last_n_days"}),
    ("deal.expected_close", "relative", {"period": "this_year", "days": 5}),
    ("deal.expected_close", "relative", {"period": "nope"}),
    ("deal.expected_close", "relative", {"period": "last_3_months", "days": 5}),
    ("deal.expected_close", "relative", {"period": "last_1_month", "days": 1}),
    ("deal.expected_close", "relative", {"period": "last_6_months", "days": 0}),
    ("deal.expected_close", "relative", "this_year"),
]


@pytest.mark.parametrize(("field", "operator", "value"), INVALID)
def test_condition_value_shapes_are_checked_per_operator(
    field: str, operator: str, value: object
) -> None:
    """연산자마다 값 모양이 틀리면 그 조건의 value 위치로 value-invalid다.

    테스트 코드: RQ-024
    """
    # when: 틀린 값의 조건 하나를 검증한다 (전제: 값 변형 매개변수)
    found = _only_condition_issue(field, operator, value)
    # then: value-invalid 하나다
    assert found == [(("conditions", 0, "value"), "value-invalid")]


@pytest.mark.parametrize(
    ("field", "operator", "value"),
    [
        ("deal.vendor", "in", list(range(1, 101))),
        ("deal.name", "contains", "x" * 200),
        ("deal.amount", "eq", 2**53 - 1),
        ("deal.amount", "between", [5, 5]),
        ("deal.expected_close", "between", ["2026-01-01", "2026-01-01"]),
        ("deal.expected_close", "relative", {"period": "last_n_days", "days": 1}),
        ("deal.expected_close", "relative", {"period": "last_n_days", "days": 3650}),
    ],
)
def test_value_boundaries_are_accepted(field: str, operator: str, value: object) -> None:
    """조건 값의 경계(100개·200자·±2^53-1·같은 범위·3650일)는 허용된다.

    테스트 코드: RQ-025
    """
    # when: 경계 값의 조건을 검증한다 (전제: 경계 값 매개변수)
    conditions = parse([CODE], [cond(field, operator, value)]).conditions
    # then: 조건이 받아들여진다
    assert conditions


@pytest.mark.parametrize("period", ["last_1_month", "last_3_months", "last_6_months"])
def test_month_based_relative_periods_are_accepted_without_days(period: str) -> None:
    """최근 1·3·6개월 상대 기간은 일수 없이 받아들여진다.

    테스트 코드: RQ-037
    """
    # when: 일수 없는 개월 상대 기간 조건을 검증한다
    value = (
        parse([CODE], [cond("deal.expected_close", "relative", {"period": period})])
        .conditions[0]
        .value
    )

    # then: 기간만 있고 일수는 None인 상대 값이다
    assert value == RelativeValue(period=RelativePeriod(period), days=None)


def test_text_value_is_trimmed() -> None:
    """텍스트 검색어는 앞뒤 공백을 지운 값으로 해석된다.

    테스트 코드: RQ-024
    """
    # when: 앞뒤 공백이 있는 검색어 조건을 검증한다
    value = parse([CODE], [cond("deal.name", "equals", "  Foo  ")]).conditions[0].value

    # then: 다듬은 텍스트 값이다
    assert value == TextValue(text="Foo")


def test_parsed_values_take_the_shape_of_their_operator() -> None:
    """해석된 값은 연산자의 모양(값 없음·id·key·숫자·범위·날짜·상대)을 가진다.

    테스트 코드: RQ-024
    """
    # when: 연산자 8가지의 조건을 검증한다
    conditions = parse(
        [CODE],
        [
            cond("deal.name", "is_empty"),
            cond("deal.vendor", "in", [2, 1]),
            cond("deal.status", "in", ["a", "b"]),
            cond("deal.amount", "gt", 5),
            cond("deal.amount", "between", [1, 9]),
            cond("deal.expected_close", "before", "2026-10-01"),
            cond("deal.expected_close", "between", ["2026-01-01", "2026-02-01"]),
            cond("deal.expected_close", "relative", {"period": "last_n_days", "days": 7}),
        ],
    ).conditions

    # then: 조건 값이 순서대로 연산자별 값 객체다
    from datetime import date  # noqa: PLC0415

    assert [c.value for c in conditions] == [
        NoValue(),
        IdList(ids=(2, 1)),
        KeyList(keys=("a", "b")),
        NumberValue(n=5),
        NumberRange(low=1, high=9),
        DateValue(day=date(2026, 10, 1)),
        DateRange(first=date(2026, 1, 1), last=date(2026, 2, 1)),
        RelativeValue(period=RelativePeriod.LAST_N_DAYS, days=7),
    ]


def test_every_condition_violation_is_reported_in_input_order() -> None:
    """조건 위반은 처음에 멈추지 않고 입력 순서대로 모두 알린다.

    테스트 코드: RQ-010
    """
    # when: 위반 세 개를 가진 조건 목록을 검증한다
    found = issues(
        [CODE],
        [
            cond("deal.name", "gt", "x"),
            cond("deal.vendor", "in", []),
            cond("deal.amount", "eq", True),
        ],
    )

    # then: 조건 index 순서대로 세 위반이다
    assert found == [
        (("conditions", 0, "operator"), "operator-not-allowed"),
        (("conditions", 1, "value"), "value-invalid"),
        (("conditions", 2, "value"), "value-invalid"),
    ]


# ---- 정적 선택지 밖 key ----

STATIC_FIELDS = [
    ("deal.forecast_outcome", ["open", "won", "lost"]),
    ("deal.quote_submitted", ["YES", "NO"]),
    ("deal.poc_state", ["YES", "ING", "NO"]),
    ("deal.risk", ["overdue", "stale"]),
    ("action.next_action_status", ["open", "done", "not_done"]),
]


@pytest.mark.parametrize(("field", "options"), STATIC_FIELDS, ids=[f for f, _ in STATIC_FIELDS])
@pytest.mark.parametrize("operator", ["in", "not_in"])
def test_static_option_fields_accept_every_listed_key(
    field: str, options: list[str], operator: str
) -> None:
    """정적 선택지 필드는 선택지의 모든 key를 받아들인다.

    테스트 코드: RQ-026
    """
    # when: 선택지 전체를 in·not_in으로 검증한다 (전제: 필드·연산자 매개변수)
    conditions = parse([CODE], [cond(field, operator, options)]).conditions
    # then: 조건이 받아들여진다
    assert conditions


@pytest.mark.parametrize(("field", "options"), STATIC_FIELDS, ids=[f for f, _ in STATIC_FIELDS])
@pytest.mark.parametrize("operator", ["in", "not_in"])
def test_static_option_field_rejects_a_key_outside_the_options(
    field: str, options: list[str], operator: str
) -> None:
    """정적 선택지 필드는 선택지 밖 key를 value-invalid로 거절한다.

    테스트 코드: RQ-026
    """
    # when: 선택지 밖 key를 섞은 조건을 검증한다 (전제: 필드·연산자 매개변수)
    found = issues([CODE], [cond(field, operator, [options[0], "xyz"])])

    # then: value 위치의 value-invalid 하나다
    assert found == [(("conditions", 0, "value"), "value-invalid")]


def test_risk_condition_rejects_the_combined_result_value() -> None:
    """경고 조건에 결과 값 표기(overdue_stale)는 선택지가 아니라 거절된다.

    테스트 코드: RQ-026
    """
    # when: 경고 조건에 결과 값 표기를 넣어 검증한다
    found = issues([CODE], [cond("deal.risk", "in", ["overdue_stale"])])

    # then: value 위치의 value-invalid 하나다
    assert found == [(("conditions", 0, "value"), "value-invalid")]


def test_db_backed_key_fields_do_not_check_the_key_list() -> None:
    """출처가 DB인 key 필드는 값 존재를 검사하지 않는다.

    테스트 코드: RQ-026
    """
    # when: Status·Forecast에 임의의 key를 넣어 검증한다
    status = parse([CODE], [cond("deal.status", "in", ["any_custom_key"])]).conditions
    forecast = parse([CODE], [cond("deal.forecast", "in", ["any_custom_key"])]).conditions
    # then: 두 조건이 받아들여진다
    assert status
    assert forecast
