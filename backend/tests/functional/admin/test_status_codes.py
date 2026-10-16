"""Feature: 모든 사용자는 Status 코드를 조회하고, admin은 Status 코드를 추가하며 사용 수를 확인한다.

Status는 Deal의 진행 단계다. 기본 7개(기회발굴…계약완료, lost 없음)는 마이그레이션이 넣는다.
이름 변경·순서 변경·삭제는 `test_status_code_changes.py`, 권한은 `test_code_permissions.py`.
"""

from typing import TYPE_CHECKING

import pytest

from tests.fakes.catalog_seed import DEFAULT_STATUSES, LOCKED
from tests.functional.steps.auth import RoleName, given_logged_in_as, given_logged_out
from tests.functional.steps.codes import (
    BLANK_MESSAGE,
    DUPLICATE_MESSAGE,
    given_code_created,
    given_deal_in_status,
    then_code_count_is,
    then_code_keys_are,
    then_detail_is,
    then_every_code_has_the_documented_fields,
    then_kind_order_is,
    then_location_points_to_the_created,
    then_usage_counts_are,
    then_usage_keys_are,
    when_create_code,
    when_list_code_usage,
    when_list_codes,
)
from tests.functional.steps.common import then_body_includes, then_problem_is, then_status_is

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

STATUS_KEYS = [key for key, _ in DEFAULT_STATUSES]


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_every_role_sees_the_default_status_codes_in_order(api: Api, role: RoleName) -> None:
    """Scenario: 어떤 역할이든 로그인하면 기본 Status 7개를 순서대로 본다(AC-01)."""
    # Given
    await given_logged_in_as(api, role=role)
    # When
    response = await when_list_codes(api)
    # Then
    then_status_is(response, 200)
    then_code_keys_are(response, kind="status", keys=STATUS_KEYS)
    then_every_code_has_the_documented_fields(response, kind="status")


async def test_default_status_codes_have_names_orders_and_lock_flags(api: Api) -> None:
    """Scenario: 기본 Status는 목업과 같은 이름·순서이고 기회발굴·계약완료만 잠겨 있다(AC-01·07)."""
    # Given
    await given_logged_in_as(api, role="user")
    # When
    response = await when_list_codes(api)
    # Then
    then_status_is(response, 200)
    statuses = response.json()["statuses"]
    assert [
        (c["key"], c["name"], c["order"], c["locked"], c["outcome"], c["probability_hint"])
        for c in statuses
    ] == [
        (key, name, order, ("status", key) in LOCKED, "open", None)
        for order, (key, name) in enumerate(DEFAULT_STATUSES, start=1)
    ]


async def test_anonymous_user_cannot_list_codes(api: Api) -> None:
    """Scenario: 로그인하지 않으면 코드 목록을 볼 수 없다(401)."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_logged_out(api)
    # When
    response = await when_list_codes(api)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_admin_sees_zero_usage_for_every_status_when_no_deal_exists(api: Api) -> None:
    """Scenario: Deal이 없으면 모든 Status의 사용 수가 0이다(AC-02)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_list_code_usage(api, kind="status")
    # Then
    then_status_is(response, 200)
    then_usage_keys_are(response, STATUS_KEYS)
    then_usage_counts_are(response, {})


async def test_admin_sees_how_many_deals_use_each_status(api: Api) -> None:
    """Scenario: Deal이 쓰는 Status의 사용 수는 Deal 수와 같다(AC-02, P0는 stage 기준)."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_deal_in_status(api, status_key="prospecting", number=1)
    await given_deal_in_status(api, status_key="introduction", number=2)
    await given_deal_in_status(api, status_key="introduction", number=3)
    # When
    response = await when_list_code_usage(api, kind="status")
    # Then
    then_status_is(response, 200)
    then_usage_counts_are(response, {"prospecting": 1, "introduction": 2})


async def test_admin_adds_a_status_code_at_the_end_with_a_generated_key(api: Api) -> None:
    """Scenario: admin이 이름으로 Status를 추가하면 key가 만들어지고 맨 끝에 놓인다(AC-03)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="status", name="Final Review")
    # Then
    then_status_is(response, 201)
    then_location_points_to_the_created(response)
    then_body_includes(
        response,
        kind="status",
        key="final_review",
        name="Final Review",
        order=8,
        locked=False,
        outcome="open",
        probability_hint=None,
        usage_count=0,
    )
    await then_kind_order_is(api, kind="status", keys=[*STATUS_KEYS, "final_review"])


async def test_status_code_without_english_letters_gets_a_sequential_key(api: Api) -> None:
    """Scenario: 영문이 없는 이름의 key는 code_1, code_2 순으로 만들어진다(AC-03)."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_code_created(api, kind="status", name="보류")
    # When
    response = await when_create_code(api, kind="status", name="검토 중")
    # Then
    then_status_is(response, 201)
    then_body_includes(response, key="code_2", order=9)


async def test_status_code_name_is_trimmed(api: Api) -> None:
    """Scenario: 이름의 앞뒤 공백은 지워서 저장한다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="status", name="  Final Review  ")
    # Then
    then_status_is(response, 201)
    then_body_includes(response, name="Final Review", key="final_review")


async def test_status_code_name_of_50_characters_is_accepted(api: Api) -> None:
    """Scenario: 이름 50자는 허용된다(경계, AC-04)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="status", name="가" * 50)
    # Then
    then_status_is(response, 201)
    then_body_includes(response, name="가" * 50)


@pytest.mark.parametrize("name", ["final review", "FINAL REVIEW", " Final Review "])
async def test_adding_a_status_code_with_an_existing_name_ignoring_case_conflicts(
    api: Api, name: str
) -> None:
    """Scenario: 같은 종류에 대소문자만 다른 이름을 추가하면 409다(AC-04)."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_code_created(api, kind="status", name="Final Review")
    # When
    response = await when_create_code(api, kind="status", name=name)
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    then_detail_is(response, DUPLICATE_MESSAGE)
    await then_code_count_is(api, kind="status", count=8)


async def test_adding_a_status_code_named_like_a_default_conflicts(api: Api) -> None:
    """Scenario: 기본 Status와 같은 이름도 추가할 수 없다(AC-04)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="status", name="기회발굴")
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    then_detail_is(response, DUPLICATE_MESSAGE)


async def test_status_code_may_share_a_name_with_a_forecast_code(api: Api) -> None:
    """Scenario: 이름 중복은 같은 종류 안에서만 검사한다(AC-04)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="status", name="Best")
    # Then
    then_status_is(response, 201)
    then_body_includes(response, key="best", name="Best")


@pytest.mark.parametrize("name", ["", "   "], ids=["empty", "blank"])
async def test_adding_a_status_code_without_a_name_is_rejected(api: Api, name: str) -> None:
    """Scenario: 이름이 비어 있으면 422 "이름을 입력하세요."다(AC-04)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="status", name=name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, BLANK_MESSAGE)
    await then_code_count_is(api, kind="status", count=7)


async def test_adding_a_status_code_with_a_name_over_50_characters_is_rejected(api: Api) -> None:
    """Scenario: 이름이 51자이면 422다(경계, AC-04)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="status", name="가" * 51)
    # Then
    then_status_is(response, 422)
    await then_code_count_is(api, kind="status", count=7)


async def test_adding_a_status_code_with_a_probability_hint_is_rejected(api: Api) -> None:
    """Scenario: 확률 힌트는 Forecast에만 있으므로 Status에 주면 422다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(
        api, kind="status", name="Final Review", probability_hint="10-20"
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_code_count_is(api, kind="status", count=7)
