"""Reports 필드 카탈로그: 설계 표의 40개 필드, 형식별 허용 목록, 기본값, 어휘."""

from typing import TYPE_CHECKING

import pytest

from app.domain.report.catalog import FIELD_CATALOG, find_field
from app.domain.report.vocabulary import (
    Aggregate,
    Entity,
    FieldType,
    Format,
    NumberUnit,
    Operator,
)

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
    FieldType.TEXT: set(),
    FieldType.CODE: set(),
    FieldType.USER: set(),
    FieldType.NUMBER: set(),
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
    """카탈로그는 설계 표의 40개 필드를 정해진 key 순서로 가진다.

    테스트 코드: RQ-002
    """
    # when: 카탈로그의 key 목록을 읽는다
    keys = [f.key for f in FIELD_CATALOG]
    # then: Deal 28개 뒤에 Action 12개 순서다
    assert keys == DEAL_KEYS + ACTION_KEYS


def test_catalog_has_28_deal_fields_and_12_action_fields() -> None:
    """카탈로그는 Deal 필드 28개와 Action 필드 12개를 가진다.

    테스트 코드: RQ-002
    """
    # when: 필드마다 소속 엔터티를 모은다
    entities = [f.entity for f in FIELD_CATALOG]

    # then: Deal이 28개, Action이 12개다
    assert entities.count(Entity.DEAL) == 28
    assert entities.count(Entity.ACTION) == 12


def test_each_field_key_belongs_to_its_entity_prefix() -> None:
    """필드 key의 접두어는 그 필드의 엔터티와 같다.

    테스트 코드: RQ-002
    """
    # when: 엔터티 값과 접두어가 다른 필드를 모은다
    mismatched = [f.key for f in FIELD_CATALOG if f.key.split(".")[0] != f.entity.value]
    # then: 그런 필드가 없다
    assert mismatched == []


@pytest.mark.parametrize("spec", FIELD_CATALOG, ids=lambda f: f.key)
def test_each_field_allows_only_its_type_formats_operators_and_aggregates(
    spec: FieldSpec,
) -> None:
    """필드마다 포맷·연산자·집계가 그 형식의 허용표 안에 있고 기본 포맷이 맞다.

    테스트 코드: RQ-003
    """
    # when: 필드의 포맷·연산자·집계를 읽는다 (전제: 카탈로그의 필드 하나)
    formats = set(spec.formats)
    operators = set(spec.operators)
    aggregates = set(spec.aggregates)
    expected = NUMERIC_AGGREGATES if spec.type == FieldType.NUMBER else COUNT_AGGREGATES
    # then: 허용표 안에 있고 포맷이 있으면 기본 포맷이 그 안에, 없으면 None이다
    assert formats <= ALLOWED_FORMATS[spec.type]
    if spec.formats:
        assert spec.default_format in spec.formats
    else:
        assert spec.default_format is None
    assert operators <= ALLOWED_OPERATORS[spec.type]
    assert aggregates <= expected


def test_amount_is_won_and_sums_by_default() -> None:
    """금액 필드는 원 단위이고 기본 집계가 합계이며 이름이 금액이고 Deal 숫자다.

    테스트 코드: RQ-004
    """
    # when: 금액 필드를 찾는다
    amount = find_field("deal.amount")

    # then: 단위 krw, 기본 집계 합계, 이름 금액, Deal 숫자다
    assert amount is not None
    assert amount.unit == NumberUnit.KRW
    assert amount.default_aggregate == Aggregate.SUM
    assert amount.label == "금액"
    assert amount.deal_number is True


@pytest.mark.parametrize("key", ["deal.amount", "deal.users", "deal.status_days", "action.count"])
def test_number_fields_have_no_formats(key: str) -> None:
    """숫자 필드는 포맷 목록이 비고 기본 포맷이 없다.

    테스트 코드: RQ-004
    """
    # when: 숫자 필드를 찾는다
    spec = find_field(key)

    # then: 포맷이 없다
    assert spec is not None
    assert spec.type == FieldType.NUMBER
    assert spec.formats == ()
    assert spec.default_format is None


def test_only_amount_has_a_unit() -> None:
    """단위가 있는 필드는 금액 하나뿐이다.

    테스트 코드: RQ-004
    """
    # when: 단위가 있는 필드를 모은다
    with_unit = [f.key for f in FIELD_CATALOG if f.unit is not None]

    # then: deal.amount 하나뿐이다
    assert with_unit == ["deal.amount"]


def test_format_has_only_date_formats() -> None:
    """포맷 어휘는 날짜·시각 포맷 7개뿐이다.

    테스트 코드: RQ-007
    """
    # when: 포맷 어휘를 읽는다
    values = [f.value for f in Format]
    # then: 7개이고 예전 포맷이 없다
    assert values == [
        "ymd",
        "ymd_hm",
        "year",
        "quarter",
        "month",
        "weekday",
        "relative",
    ]


def test_number_unit_has_only_krw() -> None:
    """숫자 단위 어휘는 원(krw) 하나뿐이다.

    테스트 코드: RQ-004
    """
    # when: 단위 어휘를 읽는다
    values = [u.value for u in NumberUnit]
    # then: krw 하나다
    assert values == ["krw"]


def test_status_days_defaults_to_average_and_is_a_deal_number() -> None:
    """Status 체류 일수는 기본 집계가 평균이고 Deal 숫자다.

    테스트 코드: RQ-003
    """
    # when: 체류 일수 필드를 찾는다
    days = find_field("deal.status_days")

    # then: 기본 집계 평균, Deal 숫자다
    assert days is not None
    assert days.default_aggregate == Aggregate.AVG
    assert days.deal_number is True


def test_users_is_a_deal_number_but_expected_close_is_not() -> None:
    """Users count는 Deal 숫자이고 Expected Close는 아니다.

    테스트 코드: RQ-003
    """
    # when: 두 필드의 Deal 숫자 여부를 읽는다
    users_is_deal_number = find_field("deal.users").deal_number  # type: ignore[union-attr]
    close_is_deal_number = find_field("deal.expected_close").deal_number  # type: ignore[union-attr]
    # then: users는 Deal 숫자이고 expected_close는 아니다
    assert users_is_deal_number is True
    assert close_is_deal_number is False


def test_find_field_is_exact_and_case_sensitive() -> None:
    """필드 key 찾기는 대소문자·공백까지 정확히 같을 때만 찾는다.

    테스트 코드: RQ-011
    """
    # when: 정확한 key, 대소문자·뒤 공백이 다른 key, 없는 key, 빈 문자열로 찾는다
    exact = find_field("deal.code")
    wrong_case = find_field("Deal.Code")
    trailing_space = find_field("deal.code ")
    unknown = find_field("deal.password")
    empty = find_field("")
    # then: 정확한 key만 찾고 나머지는 못 찾는다
    assert exact is not None
    assert wrong_case is None
    assert trailing_space is None
    assert unknown is None
    assert empty is None


def test_action_count_is_virtual_requires_grouping_and_is_not_filterable() -> None:
    """Action 건수는 그룹핑 전용이고 조건과 그룹 컬럼에 쓸 수 없다.

    테스트 코드: RQ-005
    """
    # when: Action 건수 필드를 찾는다
    count = find_field("action.count")

    # then: 그룹핑 필요, 조건 불가, 그룹 불가다
    assert count is not None
    assert count.requires_grouping is True
    assert count.filterable is False
    assert count.groupable is False


def test_only_action_count_requires_grouping() -> None:
    """그룹핑이 필요한 필드는 Action 건수 하나뿐이다.

    테스트 코드: RQ-005
    """
    # when: 그룹핑이 필요한 필드의 key를 모은다
    keys = [f.key for f in FIELD_CATALOG if f.requires_grouping]
    # then: action.count 하나다
    assert keys == ["action.count"]


def test_static_code_fields_carry_their_options_and_db_fields_carry_a_source() -> None:
    """정적 코드 필드는 선택지를, 출처 필드는 선택지 출처를 가진다.

    테스트 코드: RQ-006
    """
    # when: Forecast 구분·Vendor·BANT Budget 필드를 찾는다
    outcome = find_field("deal.forecast_outcome")
    vendor = find_field("deal.vendor")
    budget = find_field("deal.bant_budget")

    # then: 정적 선택지 open·won·lost, Vendor는 출처 vendors, BANT는 분류 budget이다
    assert outcome is not None
    assert [o.value for o in outcome.options or ()] == ["open", "won", "lost"]
    assert vendor is not None
    assert vendor.options is None
    assert str(vendor.options_source) == "vendors"
    assert budget is not None
    assert budget.options_category == "budget"


def test_risk_options_are_overdue_and_stale() -> None:
    """경고 필드의 선택지는 overdue와 stale 둘뿐이다.

    테스트 코드: RQ-006
    """
    # when: 경고 필드를 찾는다
    risk = find_field("deal.risk")

    # then: 선택지는 overdue, stale이다
    assert risk is not None
    assert [o.value for o in risk.options or ()] == ["overdue", "stale"]


# ---- 포맷 어휘 ----

LEGACY_FORMAT_NAMES = ["as_is", "prefix", "name", "key"]
DATE_BUCKETS = {Format.YMD, Format.YEAR, Format.QUARTER, Format.MONTH}


@pytest.mark.parametrize("field_type", [FieldType.TEXT, FieldType.CODE, FieldType.USER])
def test_text_code_user_types_have_no_formats(field_type: FieldType) -> None:
    """텍스트·코드·사용자 형식은 포맷이 없고 기본 포맷도 없다.

    테스트 코드: RQ-003
    """
    # when: 형식별 포맷 어휘를 읽는다
    from app.domain.report.vocabulary import TYPE_DEFAULT_FORMAT, TYPE_FORMATS  # noqa: PLC0415

    # then: 포맷이 비어 있고 기본값이 없다
    assert tuple(TYPE_FORMATS[field_type]) == ()
    assert TYPE_DEFAULT_FORMAT[field_type] is None


@pytest.mark.parametrize("name", LEGACY_FORMAT_NAMES)
def test_format_vocabulary_has_no_legacy_values(name: str) -> None:
    """포맷 어휘에 예전 포맷이 없고 라벨과 일치한다.

    테스트 코드: RQ-007
    """
    # when: 포맷 어휘와 라벨을 읽는다
    from app.domain.report.labels import FORMAT_LABELS  # noqa: PLC0415

    # then: 예전 이름이 없고 라벨 집합이 같으며 7개다
    assert name not in {f.value for f in Format}
    assert set(FORMAT_LABELS) == set(Format)
    assert len(Format) == 7


def test_affects_query_is_date_buckets_only() -> None:
    """SQL 묶음 단위를 바꾸는 포맷은 날짜 묶음 4개뿐이다.

    테스트 코드: RQ-007
    """
    # when: 쿼리에 영향을 주는 포맷을 모은다
    affecting = {f for f in Format if f.affects_query}
    # then: ymd·year·quarter·month뿐이다
    assert affecting == DATE_BUCKETS


@pytest.mark.parametrize(
    "spec",
    [f for f in FIELD_CATALOG if f.type in {FieldType.TEXT, FieldType.CODE, FieldType.USER}],
    ids=lambda f: f.key,
)
def test_formatless_fields_have_empty_formats_and_null_default(spec: FieldSpec) -> None:
    """포맷 없는 형식의 필드는 포맷 목록이 비고 기본 포맷이 null이다.

    테스트 코드: RQ-003
    """
    # when: 필드의 포맷 목록과 기본 포맷을 읽는다 (전제: 필드 하나)
    formats = tuple(spec.formats)
    default_format = spec.default_format
    # then: 포맷 목록이 비고 기본값이 null이다
    assert formats == ()
    assert default_format is None


DATE_CONVERTED_KEYS = [
    "deal.last_updated_at",
    "deal.status_changed_at",
    "action.acted_at",
    "action.closed_at",
]


@pytest.mark.parametrize("key", DATE_CONVERTED_KEYS)
def test_converted_fields_are_dates_with_ymd_default_and_no_time_format(key: str) -> None:
    """최종 업데이트·Status 진입일·수행일·종료일은 date 형식이고 기본 포맷 ymd이며 ymd_hm이 없다.

    테스트 코드: RQ-113
    """
    # when: key(기존 그대로)로 필드를 찾는다
    spec = find_field(key)

    # then: date 형식, 포맷은 date 허용표, 기본 ymd, ymd_hm 없음
    assert spec is not None
    assert spec.type == FieldType.DATE
    assert set(spec.formats) == ALLOWED_FORMATS[FieldType.DATE]
    assert spec.default_format == Format.YMD
    assert Format.YMD_HM not in spec.formats


def test_converted_fields_have_date_labels() -> None:
    """표시 이름이 시각을 뜻하지 않는다: 최종 업데이트, Status 진입일, 수행일, 종료일.

    테스트 코드: RQ-113
    """
    # when: 네 필드의 표시 이름을 읽는다
    labels = [find_field(key).label for key in DATE_CONVERTED_KEYS]  # type: ignore[union-attr]
    # then: 날짜 이름이다
    assert labels == ["최종 업데이트", "Status 진입일", "수행일", "종료일"]


def test_created_at_is_the_only_datetime_field() -> None:
    """시각(datetime) 형식 필드는 등록일(deal.created_at) 하나뿐이다.

    테스트 코드: RQ-113
    """
    # when: datetime 형식 필드를 모은다
    keys = [f.key for f in FIELD_CATALOG if f.type == FieldType.DATETIME]
    # then: deal.created_at 하나다
    assert keys == ["deal.created_at"]
