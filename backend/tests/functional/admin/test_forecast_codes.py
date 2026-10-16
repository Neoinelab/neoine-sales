"""Feature: 모든 사용자는 Forecast 코드를 조회하고, admin은 관리하되 시스템 코드는 못 지운다.

기본 6개(Pipeline·Best·Most Likely·Commit·Won·Lost)는 마이그레이션이 넣는다. 잠긴 Forecast는
Pipeline·Won·Lost다. 새 코드는 outcome이 open이고 확률 힌트를 가질 수 있다. P0에서는 Deal이
Forecast를 쓰지 않으므로 사용 수는 항상 0이다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.fakes.catalog_seed import DEFAULT_FORECASTS, LOCKED
from tests.functional.steps.auth import RoleName, given_logged_in_as
from tests.functional.steps.codes import (
    DUPLICATE_MESSAGE,
    LOCKED_MESSAGE,
    REORDER_MESSAGE,
    given_code_id,
    given_code_ids,
    then_code_count_is,
    then_code_exists,
    then_code_is_gone,
    then_code_keys_are,
    then_code_name_is,
    then_detail_is,
    then_every_code_has_the_documented_fields,
    then_kind_order_is,
    then_usage_counts_are,
    then_usage_keys_are,
    when_create_code,
    when_delete_code,
    when_list_code_usage,
    when_list_codes,
    when_rename_code,
    when_reorder_codes,
)
from tests.functional.steps.common import then_body_includes, then_problem_is, then_status_is

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

FORECAST_KEYS = [key for key, *_ in DEFAULT_FORECASTS]


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_every_role_sees_the_default_forecast_codes_in_order(
    api: Api, role: RoleName
) -> None:
    """Scenario: 어떤 역할이든 로그인하면 기본 Forecast 6개를 순서대로 본다(AC-01)."""
    # Given
    await given_logged_in_as(api, role=role)
    # When
    response = await when_list_codes(api)
    # Then
    then_status_is(response, 200)
    then_code_keys_are(response, kind="forecast", keys=FORECAST_KEYS)
    then_every_code_has_the_documented_fields(response, kind="forecast")


async def test_default_forecast_codes_have_outcomes_hints_and_lock_flags(api: Api) -> None:
    """Scenario: 기본 Forecast는 목업과 같은 이름·확률 힌트·결과이고 3개가 잠겨 있다(AC-01·07)."""
    # Given
    await given_logged_in_as(api, role="user")
    # When
    response = await when_list_codes(api)
    # Then
    then_status_is(response, 200)
    forecasts = response.json()["forecasts"]
    assert [
        (c["key"], c["name"], c["order"], c["locked"], c["outcome"], c["probability_hint"])
        for c in forecasts
    ] == [
        (key, name, order, ("forecast", key) in LOCKED, outcome, hint)
        for order, (key, name, outcome, hint) in enumerate(DEFAULT_FORECASTS, start=1)
    ]


async def test_admin_sees_zero_usage_for_every_forecast_code(api: Api) -> None:
    """Scenario: P0에서는 Forecast 사용 수가 모두 0이다(AC-02)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_list_code_usage(api, kind="forecast")
    # Then
    then_status_is(response, 200)
    then_usage_keys_are(response, FORECAST_KEYS)
    then_usage_counts_are(response, {})


async def test_admin_adds_a_forecast_code_with_a_probability_hint(api: Api) -> None:
    """Scenario: Forecast를 추가하면 outcome은 open이고 확률 힌트가 저장된다(AC-03)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="forecast", name="Upside", probability_hint="10-20")
    # Then
    then_status_is(response, 201)
    then_body_includes(
        response,
        kind="forecast",
        key="upside",
        name="Upside",
        order=7,
        locked=False,
        outcome="open",
        probability_hint="10-20",
        usage_count=0,
    )
    await then_kind_order_is(api, kind="forecast", keys=[*FORECAST_KEYS, "upside"])


async def test_forecast_code_may_be_added_without_a_probability_hint(api: Api) -> None:
    """Scenario: 확률 힌트는 선택이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="forecast", name="Upside")
    # Then
    then_status_is(response, 201)
    then_body_includes(response, probability_hint=None)


async def test_forecast_hint_of_20_characters_is_accepted(api: Api) -> None:
    """Scenario: 확률 힌트 20자는 허용된다(경계)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(
        api, kind="forecast", name="Upside", probability_hint="9" * 20
    )
    # Then
    then_status_is(response, 201)


async def test_forecast_hint_of_21_characters_is_rejected(api: Api) -> None:
    """Scenario: 확률 힌트가 21자이면 422다(경계)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(
        api, kind="forecast", name="Upside", probability_hint="9" * 21
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_code_count_is(api, kind="forecast", count=6)


async def test_adding_a_forecast_code_with_an_existing_name_ignoring_case_conflicts(
    api: Api,
) -> None:
    """Scenario: 기본 Forecast와 대소문자만 다른 이름을 추가하면 409다(AC-04)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="forecast", name="commit")
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    then_detail_is(response, DUPLICATE_MESSAGE)
    await then_code_count_is(api, kind="forecast", count=6)


async def test_forecast_key_collision_gets_a_numeric_suffix(api: Api) -> None:
    """Scenario: 이름이 다르지만 key가 겹치면 key에 번호가 붙는다(AC-03)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="forecast", name="Best!")
    # Then
    then_status_is(response, 201)
    then_body_includes(response, key="best_2", name="Best!")


async def test_admin_renames_a_locked_forecast_code_and_its_key_stays(api: Api) -> None:
    """Scenario: 잠긴 Won도 이름을 바꿀 수 있고 key·outcome은 그대로다(AC-05)."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="forecast", key="won")
    # When
    response = await when_rename_code(api, code_id=code_id, name="수주")
    # Then
    then_status_is(response, 200)
    then_body_includes(response, key="won", name="수주", locked=True, outcome="won")
    await then_code_name_is(api, kind="forecast", key="won", name="수주")


async def test_admin_reorders_forecast_codes(api: Api) -> None:
    """Scenario: Forecast 순서를 바꾸면 order가 1부터 다시 매겨진다(AC-06)."""
    # Given
    await given_logged_in_as(api, role="admin")
    ids = await given_code_ids(api, kind="forecast")
    # When
    response = await when_reorder_codes(api, kind="forecast", ordered_ids=list(reversed(ids)))
    # Then
    then_status_is(response, 200)
    assert [c["order"] for c in response.json()] == [1, 2, 3, 4, 5, 6]
    await then_kind_order_is(api, kind="forecast", keys=list(reversed(FORECAST_KEYS)))


async def test_reordering_forecast_codes_with_a_status_id_is_rejected(api: Api) -> None:
    """Scenario: Forecast 순서 목록에 Status id가 섞이면 422다(AC-06)."""
    # Given
    await given_logged_in_as(api, role="admin")
    ids = await given_code_ids(api, kind="forecast")
    foreign = (await given_code_ids(api, kind="status"))[0]
    # When
    response = await when_reorder_codes(api, kind="forecast", ordered_ids=[*ids[:-1], foreign])
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, REORDER_MESSAGE)
    await then_kind_order_is(api, kind="forecast", keys=FORECAST_KEYS)


@pytest.mark.parametrize("key", ["pipeline", "won", "lost"])
async def test_admin_cannot_delete_a_locked_forecast_code(api: Api, key: str) -> None:
    """Scenario: Pipeline·Won·Lost는 참조가 없어도 삭제할 수 없다(409, AC-07)."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="forecast", key=key)
    # When
    response = await when_delete_code(api, code_id=code_id)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_detail_is(response, LOCKED_MESSAGE)
    await then_code_exists(api, kind="forecast", key=key)


async def test_admin_deletes_an_unlocked_forecast_code(api: Api) -> None:
    """Scenario: 잠기지 않고 쓰이지 않는 Best는 삭제된다(204, AC-08)."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="forecast", key="best")
    # When
    response = await when_delete_code(api, code_id=code_id)
    # Then
    then_status_is(response, 204)
    await then_code_is_gone(api, kind="forecast", key="best")
    await then_code_count_is(api, kind="forecast", count=5)
