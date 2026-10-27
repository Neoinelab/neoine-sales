"""Reports 필드 카탈로그 (AC1): 설계 표의 필드, 형식별 허용 목록, 기본값.

계획 4.3 표를 정본으로 한다(Deal 28 + Action 12 = 40개). key 목록이 표와 정확히 같은지를 본다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.report.catalog import FIELD_CATALOG, find_field
from app.domain.report.vocabulary import Aggregate, Entity, FieldType, Format, Operator

if TYPE_CHECKING:
    from app.domain.report.fields import FieldSpec

DEAL_KEYS = [
    "deal.code",
    "deal.name",
    "deal.solution",
    "deal.procurement",
    "deal.owner",
    "deal.customer_company",
    "deal.customer_contact",
    "deal.partner_company",
    "deal.vendor",
    "deal.status",
    "deal.forecast",
    "deal.forecast_outcome",
    "deal.quote_submitted",
    "deal.poc_state",
    "deal.bant_budget",
    "deal.bant_authority",
    "deal.bant_need",
    "deal.bant_timeline",
    "deal.risk",
    "deal.amount",
    "deal.users",
    "deal.status_days",
    "deal.expected_close",
    "deal.quote_submitted_date",
    "deal.poc_completed_date",
    "deal.created_at",
    "deal.last_updated_at",
    "deal.status_changed_at",
]
ACTION_KEYS = [
    "action.action",
    "action.next_action",
    "action.memo",
    "action.actor",
    "action.type",
    "action.next_action_status",
    "action.status",
    "action.forecast",
    "action.due_date",
    "action.acted_at",
    "action.closed_at",
    "action.count",
]
ALLOWED_FORMATS = {
    FieldType.TEXT: {Format.AS_IS, Format.PREFIX},
    FieldType.CODE: {Format.NAME, Format.KEY},
    FieldType.USER: {Format.NAME},
    FieldType.NUMBER: {
        Format.THOUSANDS,
        Format.KRW_THOUSAND,
        Format.KRW_MILLION,
        Format.DECIMAL1,
        Format.PERCENT_SHARE,
    },
    FieldType.DATE: {
        Format.YMD,
        Format.YEAR,
        Format.QUARTER,
        Format.MONTH,
        Format.WEEKDAY,
        Format.RELATIVE,
    },
    FieldType.DATETIME: {
        Format.YMD_HM,
        Format.YMD,
        Format.YEAR,
        Format.QUARTER,
        Format.MONTH,
        Format.WEEKDAY,
        Format.RELATIVE,
    },
}
ALLOWED_OPERATORS = {
    FieldType.TEXT: {
        Operator.CONTAINS,
        Operator.EQUALS,
        Operator.STARTS_WITH,
        Operator.IS_EMPTY,
        Operator.IS_NOT_EMPTY,
    },
    FieldType.CODE: {Operator.IN, Operator.NOT_IN, Operator.IS_EMPTY},
    FieldType.USER: {Operator.IN, Operator.NOT_IN, Operator.IS_EMPTY},
    FieldType.NUMBER: {
        Operator.EQ,
        Operator.NE,
        Operator.GT,
        Operator.GTE,
        Operator.LT,
        Operator.LTE,
        Operator.BETWEEN,
    },
    FieldType.DATE: {Operator.BETWEEN, Operator.BEFORE, Operator.AFTER, Operator.RELATIVE},
    FieldType.DATETIME: {Operator.BETWEEN, Operator.BEFORE, Operator.AFTER, Operator.RELATIVE},
}
NUMERIC_AGGREGATES = {Aggregate.SUM, Aggregate.AVG, Aggregate.MIN, Aggregate.MAX}
COUNT_AGGREGATES = {Aggregate.COUNT, Aggregate.COUNT_DISTINCT}


def test_catalog_has_the_40_fields_of_the_design() -> None:
    assert [f.key for f in FIELD_CATALOG] == DEAL_KEYS + ACTION_KEYS


def test_catalog_has_28_deal_fields_and_12_action_fields() -> None:
    entities = [f.entity for f in FIELD_CATALOG]

    assert entities.count(Entity.DEAL) == 28
    assert entities.count(Entity.ACTION) == 12


def test_each_field_key_belongs_to_its_entity_prefix() -> None:
    assert all(f.key.split(".")[0] == f.entity.value for f in FIELD_CATALOG)


@pytest.mark.parametrize("spec", FIELD_CATALOG, ids=lambda f: f.key)
def test_each_field_allows_only_its_type_formats_operators_and_aggregates(
    spec: FieldSpec,
) -> None:
    assert set(spec.formats) <= ALLOWED_FORMATS[spec.type]
    assert spec.default_format in spec.formats
    assert set(spec.operators) <= ALLOWED_OPERATORS[spec.type]
    expected = NUMERIC_AGGREGATES if spec.type == FieldType.NUMBER else COUNT_AGGREGATES
    assert set(spec.aggregates) <= expected


def test_amount_defaults_to_krw_thousand_and_sum() -> None:
    amount = find_field("deal.amount")

    assert amount is not None
    assert amount.default_format == Format.KRW_THOUSAND
    assert amount.default_aggregate == Aggregate.SUM
    assert amount.deal_number is True


def test_status_days_defaults_to_average_and_is_a_deal_number() -> None:
    days = find_field("deal.status_days")

    assert days is not None
    assert days.default_aggregate == Aggregate.AVG
    assert days.deal_number is True


def test_users_is_a_deal_number_but_expected_close_is_not() -> None:
    assert find_field("deal.users").deal_number is True  # type: ignore[union-attr]
    assert find_field("deal.expected_close").deal_number is False  # type: ignore[union-attr]


def test_find_field_is_exact_and_case_sensitive() -> None:
    assert find_field("deal.code") is not None
    assert find_field("Deal.Code") is None
    assert find_field("deal.code ") is None
    assert find_field("deal.password") is None
    assert find_field("") is None


def test_action_count_is_virtual_requires_grouping_and_is_not_filterable() -> None:
    count = find_field("action.count")

    assert count is not None
    assert count.requires_grouping is True
    assert count.filterable is False
    assert count.groupable is False


def test_only_action_count_requires_grouping() -> None:
    assert [f.key for f in FIELD_CATALOG if f.requires_grouping] == ["action.count"]


def test_static_code_fields_carry_their_options_and_db_fields_carry_a_source() -> None:
    outcome = find_field("deal.forecast_outcome")
    vendor = find_field("deal.vendor")
    budget = find_field("deal.bant_budget")

    assert outcome is not None
    assert [o.value for o in outcome.options or ()] == ["open", "won", "lost"]
    assert vendor is not None
    assert vendor.options is None
    assert str(vendor.options_source) == "vendors"
    assert budget is not None
    assert budget.options_category == "budget"


def test_risk_options_are_overdue_and_stale() -> None:
    risk = find_field("deal.risk")

    assert risk is not None
    assert [o.value for o in risk.options or ()] == ["overdue", "stale"]
