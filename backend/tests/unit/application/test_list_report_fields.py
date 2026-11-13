"""ListReportFields: 필드 카탈로그와 한도를 DB·시계 없이 돌려준다."""

import pytest

from app.application.report.list_fields import ListReportFields
from app.domain.report.catalog import FIELD_CATALOG
from app.domain.report.vocabulary import FieldType, NumberUnit


def test_list_report_fields_returns_the_whole_catalog() -> None:
    """필드 목록 유스케이스는 카탈로그 전체를 순서대로 돌려준다.

    테스트 코드: RQ-002
    """
    # when: 필드 목록을 조회한다
    view = ListReportFields().execute()

    # then: 필드 key 순서가 카탈로그와 같다
    assert [f.key for f in view.fields] == [f.key for f in FIELD_CATALOG]


def test_list_report_fields_returns_the_limits_of_the_design() -> None:
    """필드 목록 유스케이스는 설계의 한도 값을 돌려준다.

    테스트 코드: RQ-007
    """
    # when: 필드 목록의 한도를 조회한다
    limits = ListReportFields().execute().limits

    # then: 컬럼 1~30, 조건 20, 행 수 100·1000·10000(기본 1000), 제한 10초,
    # then: 텍스트 200·목록 100·최근 N일 3650·표시 이름 100·앞 N자 200이다
    assert limits.columns_min == 1
    assert limits.columns_max == 30
    assert limits.conditions_max == 20
    assert tuple(limits.row_limits) == (100, 1000, 10000)
    assert limits.default_row_limit == 1000
    assert limits.statement_timeout_seconds == 10
    assert limits.text_value_max == 200
    assert limits.list_value_max == 100
    assert limits.last_n_days_max == 3650
    assert limits.label_max == 100
    assert limits.prefix_max == 200


def test_catalog_fields_without_formats_have_null_default() -> None:
    """텍스트·코드·사용자·숫자 필드는 포맷 목록이 비고 기본 포맷이 null이다.

    테스트 코드: RQ-003
    """
    # when: 필드 목록을 조회한다
    fields = ListReportFields().execute().fields
    # then: 해당 형식의 모든 필드가 포맷 없음·기본값 null이다
    formatless = [
        f
        for f in fields
        if f.type in {FieldType.TEXT, FieldType.CODE, FieldType.USER, FieldType.NUMBER}
    ]

    assert formatless
    assert all(tuple(f.formats) == () and f.default_format is None for f in formatless)


def test_catalog_fields_carry_the_unit_and_only_amount_has_one() -> None:
    """금액만 원 단위를 가지고 이름이 금액이다.

    테스트 코드: RQ-004
    """
    # when: 필드 목록을 조회한다
    fields = ListReportFields().execute().fields

    # then: 금액은 krw, 이름 금액이고 단위가 있는 필드는 금액 하나다
    amount = next(f for f in fields if f.key == "deal.amount")
    assert amount.unit == NumberUnit.KRW
    assert amount.label == "금액"
    assert [f.key for f in fields if f.unit is not None] == ["deal.amount"]


def test_catalog_formats_are_seven_date_formats_and_query_affecting_ones_are_date_buckets() -> None:
    """포맷 어휘는 날짜·시각 포맷 7개이고 SQL에 영향을 주는 것은 날짜 묶음 4개뿐이다.

    테스트 코드: RQ-007
    """
    # when: 필드 목록을 조회한다
    view = ListReportFields().execute()

    # then: 포맷 7개 순서, 묶음 포맷 4개, 예전 포맷 없음, 앞 N자 한도 200이다
    assert [f.key.value for f in view.formats] == [
        "ymd",
        "ymd_hm",
        "year",
        "quarter",
        "month",
        "weekday",
        "relative",
    ]
    assert {f.key.value for f in view.formats if f.affects_query} == {
        "ymd",
        "year",
        "quarter",
        "month",
    }
    assert not {"as_is", "prefix", "name", "key"} & {f.key.value for f in view.formats}
    assert view.limits.prefix_max == 200


def test_relative_periods_are_listed_in_the_selection_order_with_labels() -> None:
    """상대 기간은 선택 순서와 이름, 일수 필요 여부와 함께 나열된다.

    테스트 코드: RQ-007
    """
    # when: 필드 목록을 조회한다
    periods = ListReportFields().execute().relative_periods

    # then: 8개가 순서대로이고 일수가 필요한 것은 최근 N일뿐이다
    assert [(p.key.value, p.label, p.needs_days) for p in periods] == [
        ("last_1_month", "최근 1개월", False),
        ("last_3_months", "최근 3개월", False),
        ("last_6_months", "최근 6개월", False),
        ("this_year", "올해", False),
        ("this_quarter", "이번 분기", False),
        ("this_month", "이번 달", False),
        ("last_n_days", "최근 N일", True),
        ("before_today", "오늘 이전", False),
    ]


@pytest.mark.parametrize(
    "key",
    ["deal.last_updated_at", "deal.status_changed_at", "action.acted_at", "action.closed_at"],
)
def test_catalog_lists_the_four_converted_fields_as_dates_without_a_time_format(key: str) -> None:
    """카탈로그 조회에서 네 필드는 date 형식, 기본 포맷 ymd이고 ymd_hm이 선택지에 없다.

    테스트 코드: RQ-113
    """
    # when: 필드 목록을 조회한다
    fields = ListReportFields().execute().fields

    # then: key는 그대로이고 형식은 date, 기본 포맷 ymd, 포맷 선택지에 ymd_hm이 없다
    field = next(f for f in fields if f.key == key)
    assert field.type.value == "date"
    assert field.default_format is not None
    assert field.default_format.value == "ymd"
    assert "ymd_hm" not in {f.value for f in field.formats}
