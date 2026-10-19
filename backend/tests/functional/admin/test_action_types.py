"""Feature: 모든 사용자는 Action 유형을 보고, sales·admin은 새 유형을 만들 수 있다.

Action 유형은 Next Action의 분류 선택지다. 기본 유형 8개(통화·미팅·이메일·데모·제안·협상·계약·
기타)는 마이그레이션이 넣는다. 이름 변경·삭제는 admin만이고 `test_action_type_changes.py`가 다룬다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.action_types import (
    DEFAULT_ORDER,
    DUPLICATE_MESSAGE,
    REQUIRED_MESSAGE,
    TOO_LONG_MESSAGE,
    given_type_created,
    then_every_type_has_the_documented_fields,
    then_location_points_to_the_created,
    then_type_count_is,
    then_type_creator_is,
    then_type_names_are,
    then_types_are_the_defaults,
    when_create_type,
    when_delete_user_account,
    when_list_types,
)
from tests.functional.steps.auth import RoleName, given_logged_in_as, given_logged_out
from tests.functional.steps.common import (
    then_body_includes,
    then_problem_is,
    then_status_is,
)
from tests.functional.steps.labels import given_current_user_id

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_everyone_signed_in_sees_default_types_in_order(api: Api, role: RoleName) -> None:
    """Scenario: 어떤 역할이든 기본 Action 유형 8개를 시드 순서대로 본다(AC-1)."""
    # Given
    await given_logged_in_as(api, role=role)
    # When
    response = await when_list_types(api)
    # Then
    then_status_is(response, 200)
    then_types_are_the_defaults(response)
    then_every_type_has_the_documented_fields(response)
    assert len(response.json()) == 8


async def test_anonymous_user_cannot_list_types(api: Api) -> None:
    """Scenario: 로그인하지 않으면 유형 목록이 401이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_logged_out(api)
    # When
    response = await when_list_types(api)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


@pytest.mark.parametrize("role", ["sales", "admin"])
async def test_sales_and_admin_create_a_type_and_are_recorded_as_its_creator(
    api: Api, role: RoleName
) -> None:
    """Scenario: sales·admin이 유형을 만들면 201, Location, 생성자 기록, 기본 유형 뒤에 놓인다."""
    # Given
    await given_logged_in_as(api, role=role)
    me = await given_current_user_id(api)
    # When
    response = await when_create_type(api, "  웨비나  ")
    # Then
    then_status_is(response, 201)
    then_location_points_to_the_created(response)
    then_body_includes(response, name="웨비나", is_default=False, usage_count=0)
    assert response.json()["created_by"]["id"] == me
    await then_type_names_are(api, [*DEFAULT_ORDER, "웨비나"])


async def test_user_cannot_create_a_type(api: Api) -> None:
    """Scenario: 읽기 전용 user는 유형을 만들 수 없다(403)."""
    # Given
    await given_logged_in_as(api, role="user")
    # When
    response = await when_create_type(api, "웨비나")
    # Then
    then_status_is(response, 403)
    await then_type_count_is(api, 8)


async def test_anonymous_user_cannot_create_a_type(api: Api) -> None:
    """Scenario: 로그인하지 않고 유형을 만들면 401이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_logged_out(api)
    # When
    response = await when_create_type(api, "웨비나")
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_custom_types_follow_the_defaults_sorted_by_lower_name(api: Api) -> None:
    """Scenario: 직접 만든 유형은 기본 유형 뒤에 소문자 이름순으로 나온다."""
    # Given
    await given_logged_in_as(api, role="sales")
    for name in ("나중에", "가장 먼저", "Zeta", "alpha"):
        await given_type_created(api, name)
    # When
    response = await when_list_types(api)
    # Then
    names = [x["name"] for x in response.json()]
    assert names == [*DEFAULT_ORDER, "alpha", "Zeta", "가장 먼저", "나중에"]


@pytest.mark.parametrize("duplicate", ["demo", " DEMO ", "미팅", " 미팅 "])
async def test_a_name_equal_to_an_existing_one_ignoring_case_is_rejected(
    api: Api, duplicate: str
) -> None:
    """Scenario: 기존 유형과 대소문자만 다른(또는 기본 유형과 같은) 이름은 409다(AC-4)."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_type_created(api, "Demo")
    # When
    response = await when_create_type(api, duplicate)
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    assert response.json()["detail"] == DUPLICATE_MESSAGE
    await then_type_count_is(api, 9)


@pytest.mark.parametrize(
    ("name", "message"),
    [
        pytest.param("   ", REQUIRED_MESSAGE, id="blank"),
        pytest.param("", REQUIRED_MESSAGE, id="empty"),
        pytest.param("가" * 51, TOO_LONG_MESSAGE, id="51-chars"),
    ],
)
async def test_invalid_names_are_rejected_with_the_user_message(
    api: Api, name: str, message: str
) -> None:
    """Scenario: 공백뿐이거나 51자인 이름은 422이고 문구가 정해져 있다(AC-3)."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_create_type(api, name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == message
    await then_type_count_is(api, 8)


async def test_a_name_of_exactly_50_characters_is_accepted(api: Api) -> None:
    """Scenario: 50자 이름은 통과한다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_create_type(api, "가" * 50)
    # Then
    then_status_is(response, 201)
    assert response.json()["name"] == "가" * 50


async def test_a_nul_character_in_the_name_is_rejected(api: Api) -> None:
    """Scenario: NUL 문자가 든 이름은 422이고 서버 오류가 아니다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_create_type(api, "웨\x00비나")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_type_count_is(api, 8)


async def test_deleting_a_user_who_created_a_type_resigns_the_user(api: Api) -> None:
    """Scenario: 유형을 만든 사용자를 삭제하면 지우지 않고 퇴사 처리된다(AC-36)."""
    # Given
    await given_logged_in_as(api, role="sales")
    sales_id = await given_current_user_id(api)
    await given_type_created(api, "웨비나")
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_user_account(api, user_id=sales_id)
    # Then
    then_status_is(response, 200)
    assert response.json() == {"outcome": "resigned"}
    await then_type_creator_is(api, name="웨비나", user_id=sales_id, resigned=True)
