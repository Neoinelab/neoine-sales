"""리포트 정의 검증의 조건 규칙 (AC4, AC8, Q4): 형식별 연산자, 연산자별 값 모양, 해석된 값 객체."""

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
    code = "unknown-field" if field == "deal.nothing" else "operator-not-allowed"
    location = "field" if field == "deal.nothing" else "operator"

    assert _only_condition_issue(field, operator, "x") == [(("conditions", 0, location), code)]


@pytest.mark.parametrize(("field", "operator", "value"), VALID)
def test_valid_condition_shapes_are_accepted(field: str, operator: str, value: object) -> None:
    definition = parse([CODE], [cond(field, operator, value)])

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
    ("deal.expected_close", "relative", "this_year"),
]


@pytest.mark.parametrize(("field", "operator", "value"), INVALID)
def test_condition_value_shapes_are_checked_per_operator(
    field: str, operator: str, value: object
) -> None:
    assert _only_condition_issue(field, operator, value) == [
        (("conditions", 0, "value"), "value-invalid")
    ]


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
    assert parse([CODE], [cond(field, operator, value)]).conditions


def test_text_value_is_trimmed() -> None:
    value = parse([CODE], [cond("deal.name", "equals", "  Foo  ")]).conditions[0].value

    assert value == TextValue(text="Foo")


def test_parsed_values_take_the_shape_of_their_operator() -> None:
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
    found = issues(
        [CODE],
        [
            cond("deal.name", "gt", "x"),
            cond("deal.vendor", "in", []),
            cond("deal.amount", "eq", True),
        ],
    )

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
    assert parse([CODE], [cond(field, operator, options)]).conditions


@pytest.mark.parametrize(("field", "options"), STATIC_FIELDS, ids=[f for f, _ in STATIC_FIELDS])
@pytest.mark.parametrize("operator", ["in", "not_in"])
def test_static_option_field_rejects_a_key_outside_the_options(
    field: str, options: list[str], operator: str
) -> None:
    found = issues([CODE], [cond(field, operator, [options[0], "xyz"])])

    assert found == [(("conditions", 0, "value"), "value-invalid")]


def test_risk_condition_rejects_the_combined_result_value() -> None:
    found = issues([CODE], [cond("deal.risk", "in", ["overdue_stale"])])

    assert found == [(("conditions", 0, "value"), "value-invalid")]


def test_db_backed_key_fields_do_not_check_the_key_list() -> None:
    assert parse([CODE], [cond("deal.status", "in", ["any_custom_key"])]).conditions
    assert parse([CODE], [cond("deal.forecast", "in", ["any_custom_key"])]).conditions
