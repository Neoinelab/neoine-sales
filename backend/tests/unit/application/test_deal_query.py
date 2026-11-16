"""DealQuery 검증: 기본값, 페이지, 최종 업데이트 기간(양끝 포함), 텍스트 정규화·길이.

연/분기(`year`·`quarter`)의 검증은 `revenue_window` 쪽 테스트가 맡는다.
"""

from dataclasses import fields
from datetime import UTC, date, datetime

import pytest

from app.application.ports.deal_repository import DealQuery, DealSort, SortOrder
from app.application.ports.pagination import MAX_LIMIT
from app.domain.common.errors import InvalidValueError
from app.domain.vendor.values import VendorId
from tests.support.expect import raises_with
from tests.support.user_ids import uid

KEYWORD_LIMIT = 100
VENDOR = VendorId(31)


def test_defaults_are_the_first_page_of_twenty_newest_first_without_conditions() -> None:
    """조건 없는 기본 조회는 최신순 첫 페이지 20건이다."""
    # when: 조건 없이 DealQuery를 만든다
    query = DealQuery()

    # then: 첫 페이지 20건, 최종 업데이트 내림차순이고 조건은 모두 비어 있다
    assert (query.offset, query.limit) == (0, 20)
    assert (query.sort, query.order) == (DealSort.LAST_UPDATED_AT, SortOrder.DESC)
    for condition in (
        "keyword",
        "owner_user_id",
        "vendor_id",
        "product",
        "status_key",
        "forecast_keys",
        "year",
        "quarters",
        "updated_from",
        "updated_to",
    ):
        assert getattr(query, condition) is None, condition


def test_sort_and_order_values_are_the_wire_values() -> None:
    """정렬 키와 방향의 값은 API에서 쓰는 문자열이다."""
    # when·then: 열거형 값 집합을 확인한다
    assert {s.value for s in DealSort} == {
        "name",
        "revenue_amount",
        "revenue_date",
        "last_updated_at",
        "status",
        "owner",
        "customer",
        "partner",
        "vendor",
        "forecast",
    }
    assert {o.value for o in SortOrder} == {"asc", "desc"}


def test_given_conditions_are_kept() -> None:
    """지정한 조건은 그대로 보존된다."""
    # when: 모든 조건을 지정해 DealQuery를 만든다
    query = DealQuery(
        keyword="erp",
        owner_user_id=uid("park"),
        vendor_id=VENDOR,
        product="itd",
        status_key="introduction",
        forecast_keys=frozenset({"best", "commit"}),
        updated_from=date(2026, 6, 1),
        updated_to=date(2026, 6, 30),
        offset=3,
        limit=7,
    )

    # then: 지정한 값이 그대로 남는다
    assert (query.keyword, query.owner_user_id) == ("erp", uid("park"))
    assert (query.vendor_id, query.product) == (VENDOR, "itd")
    assert (query.status_key, query.forecast_keys) == (
        "introduction",
        frozenset({"best", "commit"}),
    )
    assert (query.updated_from, query.updated_to) == (date(2026, 6, 1), date(2026, 6, 30))
    assert (query.offset, query.limit) == (3, 7)


def test_forecast_keys_default_to_none() -> None:
    """forecast_keys의 기본값은 None이다."""
    # when: 기본 DealQuery를 만든다
    result = DealQuery().forecast_keys
    # then: forecast_keys가 None이다
    assert result is None


def test_empty_forecast_keys_is_a_programming_error() -> None:
    """빈 forecast_keys는 프로그래밍 오류다."""
    # when·then: 빈 집합을 주면 ValueError가 난다
    with pytest.raises(ValueError, match="forecast_keys"):
        DealQuery(forecast_keys=frozenset())


def test_the_single_forecast_key_field_is_gone() -> None:
    """단일 forecast_key 필드는 없어졌다."""
    # when·then: 필드가 없고 인자로도 받지 않는다
    assert not hasattr(DealQuery(), "forecast_key")
    with pytest.raises(TypeError):
        DealQuery(forecast_key="commit")  # type: ignore[call-arg]


def test_the_old_conditions_are_gone() -> None:
    """예전 조건 필드들은 없어졌다."""
    # given: 기본 DealQuery
    query = DealQuery()

    # when·then: 예전 조건 이름과 stage 인자를 확인한다
    for removed in ("customer_id", "partner_id", "stage", "owner"):
        assert not hasattr(query, removed), removed
    with pytest.raises(TypeError):
        DealQuery(stage="lost")  # type: ignore[call-arg]


def test_a_negative_offset_is_rejected() -> None:
    """음수 offset은 거부한다."""
    # when·then: offset -1이면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        DealQuery(offset=-1)


@pytest.mark.parametrize("limit", [0, MAX_LIMIT + 1])
def test_a_limit_out_of_range_is_rejected(limit: int) -> None:
    """limit이 허용 범위 밖이면 거부한다."""
    # when·then: 0 또는 최대+1이면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        DealQuery(limit=limit)


@pytest.mark.parametrize("limit", [1, MAX_LIMIT])
def test_limit_boundaries_are_accepted(limit: int) -> None:
    """limit의 최솟값과 최댓값은 허용한다."""
    # when: 경계값 limit으로 DealQuery를 만든다
    result = DealQuery(limit=limit).limit
    # then: limit이 그대로 저장된다
    assert result == limit


def test_an_updated_period_whose_start_is_after_its_end_is_rejected() -> None:
    """최종 업데이트 기간의 시작이 끝보다 늦으면 거부한다."""
    # when·then: 시작 7/1, 끝 6/30이면 InvalidValueError와 안내 문구가 난다
    with raises_with(InvalidValueError, "최종 업데이트 기간의 시작은 끝보다 늦을 수 없습니다"):
        DealQuery(updated_from=date(2026, 7, 1), updated_to=date(2026, 6, 30))


@pytest.mark.parametrize(
    ("updated_from", "updated_to"),
    [
        (date(2026, 6, 1), date(2026, 6, 1)),  # 같은 날(양끝 포함이므로 하루)
        (date(2026, 6, 1), None),
        (None, date(2026, 6, 30)),
        (None, None),
    ],
)
def test_valid_updated_periods_are_accepted(
    updated_from: date | None, updated_to: date | None
) -> None:
    """유효한 최종 업데이트 기간은 그대로 받는다."""
    # when: 기간을 지정해 DealQuery를 만든다
    query = DealQuery(updated_from=updated_from, updated_to=updated_to)

    # then: 지정한 기간이 그대로 남는다
    assert (query.updated_from, query.updated_to) == (updated_from, updated_to)


@pytest.mark.parametrize("field", ["updated_from", "updated_to"])
def test_a_datetime_for_an_updated_date_is_rejected(field: str) -> None:
    """최종 업데이트 날짜에 datetime을 주면 거부한다."""
    # when·then: datetime을 주면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        DealQuery(**{field: datetime(2026, 6, 1, 9, 0, tzinfo=UTC)})  # type: ignore[arg-type]


def test_the_revenue_period_fields_no_longer_exist() -> None:
    """매출 기간 필드는 없어졌고 최종 업데이트 기간 필드만 남았다."""
    # when: DealQuery의 필드 이름을 모은다
    names = {f.name for f in fields(DealQuery)}

    # then: revenue_* 필드는 없고 updated_* 필드는 있다
    assert not {"revenue_from", "revenue_to"} & names
    assert {"updated_from", "updated_to"} <= names


def test_blank_keyword_becomes_none() -> None:
    """공백뿐인 키워드는 조건 없음이 된다."""
    # when: 공백만 든 키워드로 DealQuery를 만든다
    result = DealQuery(keyword="   ").keyword
    # then: keyword가 None이다
    assert result is None


def test_keyword_is_trimmed() -> None:
    """키워드는 앞뒤 공백을 제거한다."""
    # when: 앞뒤 공백이 든 키워드로 DealQuery를 만든다
    result = DealQuery(keyword=" erp ").keyword
    # then: 공백이 제거된 키워드가 저장된다
    assert result == "erp"


def test_keyword_allows_the_limit_and_rejects_one_over() -> None:
    """키워드는 상한까지 허용하고 하나 넘으면 거부한다."""
    # when: 상한 길이의 키워드로 DealQuery를 만든다
    result = DealQuery(keyword="a" * KEYWORD_LIMIT).keyword
    # then: 키워드가 그대로 저장된다
    assert result == "a" * KEYWORD_LIMIT
    # when·then: 상한+1이면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        DealQuery(keyword="a" * (KEYWORD_LIMIT + 1))


def test_a_nul_character_in_the_keyword_is_rejected() -> None:
    """키워드에 NUL이 있으면 거부한다."""
    # when·then: NUL이 든 키워드는 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        DealQuery(keyword="a\x00b")


def test_the_old_vendor_text_condition_and_solution_id_are_gone() -> None:
    """예전 vendor 텍스트 조건과 solution_id는 없어졌다."""
    # given: 기본 DealQuery
    query = DealQuery()

    # when·then: 필드가 없고 인자로도 받지 않는다
    assert not hasattr(query, "vendor")
    assert not hasattr(query, "solution_id")
    with pytest.raises(TypeError):
        DealQuery(vendor="SAP")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        DealQuery(solution_id=1)  # type: ignore[call-arg]


def test_product_filter_is_trimmed() -> None:
    """Product 필터는 앞뒤 공백을 제거한다."""
    # when: 앞뒤 공백이 든 product로 DealQuery를 만든다
    result = DealQuery(product=" itd ").product
    # then: 공백이 제거된 product가 저장된다
    assert result == "itd"


@pytest.mark.parametrize("raw", ["", "  ", "\t"])
def test_blank_product_filter_means_no_condition(raw: str) -> None:
    """공백뿐인 Product 필터는 조건 없음이다."""
    # when: 빈 값이나 공백만 든 product로 DealQuery를 만든다
    result = DealQuery(product=raw).product
    # then: product가 None이다
    assert result is None


def test_product_filter_allows_200_and_rejects_201() -> None:
    """Product 필터는 200자까지 허용하고 201자는 거부한다."""
    # when: 200자 product로 DealQuery를 만든다
    result = DealQuery(product="a" * 200).product
    # then: product가 그대로 저장된다
    assert result == "a" * 200
    # when·then: 201자는 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        DealQuery(product="a" * 201)


def test_product_filter_length_is_measured_after_trimming() -> None:
    """Product 필터 길이는 공백 제거 뒤에 잰다."""
    # when: 앞뒤 공백을 포함해 202자인 검색어를 만든다
    result = DealQuery(product=f" {'a' * 200} ").product
    # then: 정리된 값이 200자다
    assert result == "a" * 200
    # when·then: 정리 후 201자면 거부한다
    with pytest.raises(InvalidValueError):
        DealQuery(product=f" {'a' * 201} ")


def test_product_filter_with_nul_is_rejected() -> None:
    """Product 필터에 NUL이 있으면 거부한다."""
    # when·then: NUL이 든 값은 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        DealQuery(product="a\x00b")


def test_quarter_without_year_is_accepted() -> None:
    """연도 없이 분기만 지정해도 받는다."""
    # when: 연도 없이 2분기로 DealQuery를 만든다
    query = DealQuery(quarters=frozenset({2}))

    # then: 연도는 None이고 분기만 남는다
    assert (query.year, query.quarters) == (None, frozenset({2}))


@pytest.mark.parametrize("quarter", [0, 5])
def test_quarter_out_of_range_is_rejected_without_year(quarter: int) -> None:
    """분기가 1~4 밖이면 연도 없이도 거부한다."""
    # when·then: 0 또는 5분기면 InvalidValueError와 안내 문구가 난다
    with raises_with(InvalidValueError, "분기는 1~4 중에서 선택하세요."):
        DealQuery(quarters=frozenset({quarter}))
