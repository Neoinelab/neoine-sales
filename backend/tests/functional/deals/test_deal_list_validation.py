"""Feature: 목록 조회 조건의 경계와 검증.

텍스트 조건은 최대 100자, limit은 1~200, 최종 업데이트 기간 날짜는 YYYY-MM-DD(시작·끝 역전은
test_deal_list_updated_period). 형식이 틀린 값과 모르는
파라미터는 422(request-validation), 도메인 규칙 위반은 422(invalid-value)다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    given_deal,
    list_codes,
    when_list_deals,
    when_register_deal,
)
from tests.functional.steps.vendors import given_vendor
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_the_largest_limit_and_the_longest_text_conditions_are_accepted(api: Api) -> None:
    """Scenario: limit 200과 100자 keyword는 허용된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    paged = await when_list_deals(api, limit=200)
    keyword = await when_list_deals(api, keyword="a" * 100)
    # Then
    for response in (paged, keyword):
        then_status_is(response, 200)


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 201},
        {"offset": -1},
        {"keyword": "a" * 101},
        {"vendor_id": "SAP"},  # 이름이 아니라 정수 id여야 한다
        {"solution_id": "1"},  # 구 id 파라미터는 모르는 파라미터다
        {"vendor": "SAP"},  # 구 파라미터(이름)는 모르는 파라미터다
        {"solution": "a" * 201},  # Solution 텍스트 조건은 최대 200자다
        {"updated_from": "2026/06/01"},
        {"updated_to": "abc"},
        {"updated_from": "2026-06-01T10:00:00"},
        {"revenue_from": "2026-06-01"},  # 폐지된 파라미터는 모르는 파라미터다
        {"revenue_to": "2026-06-30"},
        {"owner_user_id": "not-an-id"},
        {"unknown": "x"},
    ],
)
async def test_out_of_range_or_malformed_conditions_are_request_validation_errors(
    api: Api, params: dict[str, str | int]
) -> None:
    """Scenario: 범위를 벗어나거나 형식이 틀린 조건은 422(request-validation)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_the_keyword_does_not_search_the_owner_name_or_the_vendor(api: Api) -> None:
    """Scenario: keyword 대상은 이름·고객·활성 파트너·code뿐이다(Owner 이름·Vendor 제외)."""
    # Given
    special = await given_vendor(api, "SpecialVendor")
    await given_logged_in_as(api, role="sales")
    await given_deal(api, name="ERP", vendor_id=special.id)
    # When
    by_owner = await when_list_deals(api, keyword="sales-user")
    by_vendor = await when_list_deals(api, keyword="SpecialVendor")
    # Then
    assert list_codes(by_owner) == []
    assert list_codes(by_vendor) == []


async def test_the_list_response_keeps_its_shape_whatever_the_conditions(api: Api) -> None:
    """Scenario: 조건이 있어도 응답은 {items, total, offset, limit} 모양이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_deal(api)
    # When
    response = await when_list_deals(api, keyword="erp", vendor_id=MISSING_ID, offset=0, limit=5)
    # Then
    assert set(response.json()) == {"items", "total", "offset", "limit"}
    assert (response.json()["offset"], response.json()["limit"]) == (0, 5)


async def test_the_owner_is_required_and_a_free_text_owner_is_not_accepted(api: Api) -> None:
    """Scenario: owner_user_id(정수)는 필수이고 이름 문자열 owner는 허용되지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    missing = await api.post("/api/v1/deals", json={})
    text_owner = await when_register_deal(api, owner="박영업")
    # Then
    then_problem_is(missing, status=422, type_suffix="request-validation")
    then_problem_is(text_owner, status=422, type_suffix="request-validation")


async def test_registration_with_a_nul_character_is_a_422_not_a_server_error(api: Api) -> None:
    """Scenario: 등록 본문에 NUL 문자가 있으면 500이 아니라 422(invalid-value)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, name="a\x00b")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")


async def test_quarter_without_year_is_no_longer_rejected(api: Api) -> None:
    """Scenario: 연도 없이 quarter만 보내도 422가 아니다(올해의 그 분기로 거른다)."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, quarter=2)
    # Then
    then_status_is(response, 200)


async def test_old_vendor_param_is_rejected(api: Api) -> None:
    """Scenario: 구 파라미터 vendor(이름)는 모르는 파라미터라 422(request-validation)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, vendor="SAP")
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
