"""Feature: 로그인한 누구나 담당자 선택용 사용자 목록을 조회한다(이메일은 숨기고 역할은 보인다)."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import USERS, given_logged_in_as, given_user_registered
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.requests import when_get
from tests.functional.steps.user_options_checks import (
    then_every_item_has_only_the_ref_fields,
    then_options_are,
)
from tests.functional.steps.users import (
    given_user_signed_in_once,
    then_names_are,
    when_list_options,
)
from tests.functional.steps.users_db import given_user_resigned

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _given_seeded_users(api: Api) -> None:
    """hong(영업)·kim(조회, 이메일 있음)은 재직, gone은 퇴사한 상태에서 영업 사용자로 로그인한다."""
    await given_user_signed_in_once(api, login_id="hong", role="sales", email="hong@corp.test")
    await given_user_signed_in_once(api, login_id="kim", role="user", email="kim@corp.test")
    await given_user_resigned(api, login_id="gone")
    await given_logged_in_as(api, role="sales")


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_every_role_can_read_the_options(api: Api, role: str) -> None:
    """Scenario: admin·영업·조회 어느 역할도 선택 목록을 읽을 수 있다."""
    # Given
    await given_logged_in_as(api, role=role)  # type: ignore[arg-type]
    # When
    response = await when_list_options(api)
    # Then
    then_status_is(response, 200)


async def test_anonymous_requests_are_401(api: Api) -> None:
    """Scenario: 로그인하지 않으면 401 unauthenticated다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_list_options(api)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_items_have_only_the_ref_fields_and_never_email(api: Api) -> None:
    """Scenario: 항목은 {id, name, resigned, label, role}만 담고 이메일은 나오지 않는다."""
    # Given
    await _given_seeded_users(api)
    # When
    response = await when_list_options(api)
    # Then
    then_every_item_has_only_the_ref_fields(response)


async def test_default_lists_active_users_only(api: Api) -> None:
    """Scenario: 기본 목록에는 재직자만 나오고 퇴사자는 빠진다."""
    # Given
    await _given_seeded_users(api)
    # When
    response = await when_list_options(api)
    # Then
    then_status_is(response, 200)
    names = {item["name"] for item in response.json()["items"]}
    assert "gone" not in names
    assert {"hong", "kim"} <= names


async def test_include_resigned_adds_resigned_users_with_the_resigned_label(api: Api) -> None:
    """Scenario: include_resigned=true는 퇴사자를 '(퇴사)' 표시와 함께 더한다."""
    # Given
    await _given_seeded_users(api)
    # When
    response = await when_list_options(api, include_resigned="true")
    # Then
    then_status_is(response, 200)
    items = {i["name"]: i for i in response.json()["items"]}
    assert items["gone"]["resigned"] is True
    assert items["gone"]["label"] == "gone(퇴사)"
    assert items["hong"]["resigned"] is False
    assert items["hong"]["label"] == "hong"


async def test_items_never_contain_a_login_id_field_or_the_login_id_of_a_named_user(
    api: Api,
) -> None:
    """Scenario: 표시 이름이 있는 사용자의 항목에는 AD 계정 아이디가 어디에도 없다."""
    # Given
    await given_user_signed_in_once(api, login_id="hong.gd", role="sales", display_name="홍길동")
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_options(api)
    # Then
    then_status_is(response, 200)
    hong = next(i for i in response.json()["items"] if i["name"] == "홍길동")
    assert "login_id" not in hong
    assert "hong.gd" not in str(response.json())


async def test_keyword_does_not_match_the_login_id_of_a_user_with_a_display_name(api: Api) -> None:
    """Scenario: 키워드는 표시 이름만 보고 AD 계정 아이디로는 찾아지지 않는다."""
    # Given
    await given_user_signed_in_once(api, login_id="hong.gd", role="sales", display_name="홍길동")
    await given_logged_in_as(api, role="sales")
    # When
    by_login_id = await when_list_options(api, keyword="hong")
    # Then
    then_names_are(by_login_id, [])


async def test_keyword_matches_the_display_name(api: Api) -> None:
    """Scenario: 키워드로 표시 이름을 찾는다."""
    # Given
    await given_user_signed_in_once(api, login_id="hong.gd", role="sales", display_name="홍길동")
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_options(api, keyword="홍")
    # Then
    then_names_are(response, ["홍길동"])


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"keyword": "HON"}, ["hong"]),
        ({"keyword": "nobody"}, []),
        ({"keyword": "gone"}, []),  # 기본은 재직자만
        ({"keyword": "gone", "include_resigned": "true"}, ["gone"]),
    ],
)
async def test_keyword_filters_by_name_ignoring_case(
    api: Api, params: dict[str, str], expected: list[str]
) -> None:
    """Scenario: 키워드는 대소문자를 구분하지 않고 퇴사자는 include_resigned일 때만 찾는다."""
    # Given
    await _given_seeded_users(api)
    # When
    response = await when_list_options(api, **params)
    # Then
    then_names_are(response, expected)


async def test_all_matching_users_are_returned_without_paging(api: Api) -> None:
    """Scenario: 200명을 넘어도 조건에 맞는 사용자를 전부 돌려준다."""
    # Given
    for n in range(205):
        await given_user_registered(api, login_id=f"bulk{n:03d}", role="sales")
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_options(api, keyword="bulk")
    # Then
    then_status_is(response, 200)
    assert len(response.json()["items"]) == 205


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 1},
        {"limit": 200},
        {"limit": "x"},
        {"include_resigned": "maybe"},
        {"foo": "1"},
        {"role": "boss"},
        {"role": "SALES"},
        {"role": ""},
    ],
)
async def test_invalid_parameters_are_422_request_validation(
    api: Api, params: dict[str, str | int]
) -> None:
    """Scenario: limit을 포함한 잘못된 쿼리 값과 알 수 없는 파라미터는 422 검증 오류다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_options(api, **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_every_item_carries_its_role_including_resigned_users(api: Api) -> None:
    """Scenario: 모든 항목에 role이 있고 퇴사자도 자기 role을 갖는다."""
    # Given
    await _given_seeded_users(api)
    # When
    response = await when_list_options(api, include_resigned="true")
    # Then
    then_status_is(response, 200)
    roles = {i["name"]: i["role"] for i in response.json()["items"]}
    assert roles["hong"] == "sales"
    assert roles["kim"] == "user"
    assert roles["gone"] == "sales"


async def test_role_sales_lists_only_active_sales_users(api: Api) -> None:
    """Scenario: role=sales는 재직 중인 영업 사용자만 돌려준다."""
    # Given
    await _given_seeded_users(api)  # hong(sales), kim(user), gone(퇴사 sales), root(admin)
    # When
    response = await when_list_options(api, role="sales")
    # Then
    then_options_are(response, [("hong", "sales")])


async def test_role_sales_with_include_resigned_adds_resigned_sales_users(api: Api) -> None:
    """Scenario: role=sales와 include_resigned=true를 함께 주면 퇴사 영업 사용자도 나온다."""
    # Given
    await _given_seeded_users(api)
    # When
    response = await when_list_options(api, role="sales", include_resigned="true")
    # Then
    then_options_are(response, [("hong", "sales"), ("gone", "sales")])


@pytest.mark.parametrize("role", ["admin", "user"])
async def test_role_filter_works_for_the_other_roles(api: Api, role: str) -> None:
    """Scenario: role 필터는 admin·user에도 같은 방식으로 적용된다."""
    # Given
    await _given_seeded_users(api)
    # When
    response = await when_list_options(api, role=role)
    # Then
    then_status_is(response, 200)
    items = response.json()["items"]
    assert items
    assert {i["role"] for i in items} == {role}


async def test_without_role_every_active_role_is_listed(api: Api) -> None:
    """Scenario: role을 주지 않으면 재직자 전체가 역할과 무관하게 나온다."""
    # Given
    await _given_seeded_users(api)
    # When
    response = await when_list_options(api)
    # Then
    then_status_is(response, 200)
    assert {i["role"] for i in response.json()["items"]} >= {"admin", "sales", "user"}


async def test_role_filter_combines_with_keyword(api: Api) -> None:
    """Scenario: role과 키워드를 함께 주면 둘 다 만족하는 사용자만 나온다."""
    # Given
    await _given_seeded_users(api)
    # When
    response = await when_list_options(api, role="sales", keyword="kim")
    # Then
    then_names_are(response, [])


async def test_the_admin_only_users_endpoint_stays_forbidden_for_non_admins(api: Api) -> None:
    """Scenario: 선택 목록은 열려 있어도 관리용 사용자 목록은 admin이 아니면 403이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_get(api, USERS)
    # Then
    then_status_is(response, 403)
