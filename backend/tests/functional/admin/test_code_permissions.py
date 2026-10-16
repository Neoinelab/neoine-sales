"""Feature: 코드(Status·Forecast) 관리와 사용 수 조회는 admin만 할 수 있다.

조회(GET /codes)는 모든 로그인 사용자가 한다(`test_status_codes.py`). 로그인하지 않았으면 403보다
먼저 401이다(AC-09). 거절된 요청은 상태를 바꾸지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.fakes.catalog_seed import DEFAULT_STATUSES
from tests.functional.steps.auth import RoleName, given_logged_in_as, given_logged_out
from tests.functional.steps.codes import (
    given_code_id,
    given_code_ids,
    then_code_count_is,
    then_code_exists,
    then_code_name_is,
    then_kind_order_is,
    when_create_code,
    when_delete_code,
    when_list_code_usage,
    when_rename_code,
    when_reorder_codes,
)
from tests.functional.steps.common import then_problem_is

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

NON_ADMIN = ["sales", "user"]
STATUS_KEYS = [key for key, _ in DEFAULT_STATUSES]


@pytest.mark.parametrize("role", NON_ADMIN)
async def test_non_admin_cannot_read_code_usage(api: Api, role: RoleName) -> None:
    """Scenario: sales·user는 사용 수 조회가 403이다(AC-09)."""
    # Given
    await given_logged_in_as(api, role=role)
    # When
    response = await when_list_code_usage(api, kind="status")
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")


@pytest.mark.parametrize("role", NON_ADMIN)
async def test_non_admin_cannot_add_a_code(api: Api, role: RoleName) -> None:
    """Scenario: sales·user는 코드를 추가할 수 없고 403이다(AC-09)."""
    # Given
    await given_logged_in_as(api, role=role)
    # When
    response = await when_create_code(api, kind="status", name="Final Review")
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    await then_code_count_is(api, kind="status", count=7)


@pytest.mark.parametrize("role", NON_ADMIN)
async def test_non_admin_cannot_rename_a_code(api: Api, role: RoleName) -> None:
    """Scenario: sales·user는 코드 이름을 바꿀 수 없고 403이다(AC-09)."""
    # Given
    await given_logged_in_as(api, role=role)
    code_id = await given_code_id(api, kind="status", key="introduction")
    # When
    response = await when_rename_code(api, code_id=code_id, name="소개")
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    await then_code_name_is(api, kind="status", key="introduction", name="제품소개")


@pytest.mark.parametrize("role", NON_ADMIN)
async def test_non_admin_cannot_reorder_codes(api: Api, role: RoleName) -> None:
    """Scenario: sales·user는 코드 순서를 바꿀 수 없고 403이다(AC-09)."""
    # Given
    await given_logged_in_as(api, role=role)
    ids = await given_code_ids(api, kind="status")
    # When
    response = await when_reorder_codes(api, kind="status", ordered_ids=list(reversed(ids)))
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    await then_kind_order_is(api, kind="status", keys=STATUS_KEYS)


@pytest.mark.parametrize("role", NON_ADMIN)
async def test_non_admin_cannot_delete_a_code(api: Api, role: RoleName) -> None:
    """Scenario: sales·user는 코드를 삭제할 수 없고 403이다(AC-09)."""
    # Given
    await given_logged_in_as(api, role=role)
    code_id = await given_code_id(api, kind="status", key="poc_completed")
    # When
    response = await when_delete_code(api, code_id=code_id)
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    await then_code_exists(api, kind="status", key="poc_completed")


async def test_anonymous_user_cannot_read_code_usage(api: Api) -> None:
    """Scenario: 로그인하지 않으면 사용 수 조회가 401이다(AC-09, 401이 403보다 먼저)."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_logged_out(api)
    # When
    response = await when_list_code_usage(api, kind="status")
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_anonymous_user_cannot_add_a_code(api: Api) -> None:
    """Scenario: 로그인하지 않으면 코드 추가가 401이다(AC-09)."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_logged_out(api)
    # When
    response = await when_create_code(api, kind="status", name="Final Review")
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_anonymous_user_cannot_rename_a_code(api: Api) -> None:
    """Scenario: 로그인하지 않으면 코드 이름 변경이 401이다(AC-09)."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="status", key="introduction")
    await given_logged_out(api)
    # When
    response = await when_rename_code(api, code_id=code_id, name="소개")
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_anonymous_user_cannot_reorder_codes(api: Api) -> None:
    """Scenario: 로그인하지 않으면 코드 순서 변경이 401이다(AC-09)."""
    # Given
    await given_logged_in_as(api, role="admin")
    ids = await given_code_ids(api, kind="status")
    await given_logged_out(api)
    # When
    response = await when_reorder_codes(api, kind="status", ordered_ids=list(reversed(ids)))
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_anonymous_user_cannot_delete_a_code(api: Api) -> None:
    """Scenario: 로그인하지 않으면 코드 삭제가 401이다(AC-09)."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="status", key="poc_completed")
    await given_logged_out(api)
    # When
    response = await when_delete_code(api, code_id=code_id)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")
