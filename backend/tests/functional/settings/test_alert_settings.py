"""Feature: admin은 Deal 미업데이트 경고 기준(일)을 정하고, 모든 역할이 그 값을 조회한다.

기준은 1~365일의 정수이며 저장한 적이 없으면 14일이다. 저장하면 저장한 admin과 서버 시각이 남고,
마지막 저장이 이긴다. 기준을 저장한 admin은 사용자 삭제 때 퇴사 처리된다.
"""

from typing import TYPE_CHECKING

import pytest

from app.web.permissions import ADMIN_DENIED
from tests.functional.steps.alerts import (
    ALERT_KEYS,
    DEFAULT_STALE_DAYS,
    then_format_is_rejected,
    then_range_is_rejected,
    then_stale_days_is,
    when_read_alert_settings,
    when_update_alert_settings,
    when_update_alert_settings_body,
)
from tests.functional.steps.auth import ADMIN_NAME, given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_body_is, then_problem_is, then_status_is
from tests.functional.steps.rereads import then_user_is_listed_as_resigned
from tests.functional.steps.settings import (
    current_user_id,
    then_updated_at_is_just_now,
    then_updated_by_is_user_ref,
)
from tests.functional.steps.users import id_of, when_delete_user

if TYPE_CHECKING:
    from tests.functional.conftest import Api
    from tests.functional.steps.auth import RoleName

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_default_threshold_is_fourteen_days(api: Api, role: RoleName) -> None:
    """Scenario: 저장한 적이 없으면 어느 역할이 조회해도 14일이고 저장 시각·저장자는 비어 있다."""
    # Given
    await given_logged_in_as(api, role=role)
    # When
    response = await when_read_alert_settings(api)
    # Then
    then_status_is(response, 200)
    then_body_is(
        response, {"stale_days": DEFAULT_STALE_DAYS, "updated_at": None, "updated_by": None}
    )


async def test_admin_saves_the_threshold_and_the_saver_and_time_are_recorded(api: Api) -> None:
    """Scenario: admin이 저장하면 값·저장한 admin·서버 시각이 응답에 나오고 다시 조회된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    api.clock.advance(120)
    # When
    response = await when_update_alert_settings(api, 7)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert set(body) == ALERT_KEYS
    assert body["stale_days"] == 7
    then_updated_by_is_user_ref(body, user_id=await current_user_id(api), name=ADMIN_NAME)
    then_updated_at_is_just_now(body)
    assert (await when_read_alert_settings(api)).json() == body


@pytest.mark.parametrize("role", ["sales", "user"])
async def test_only_admin_can_change_threshold(api: Api, role: RoleName) -> None:
    """Scenario: sales·user의 변경은 403이고 값은 그대로다."""
    # Given
    await given_logged_in_as(api, role=role)
    # When
    response = await when_update_alert_settings(api, 7)
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == ADMIN_DENIED
    await then_stale_days_is(api, DEFAULT_STALE_DAYS)


async def test_anonymous_callers_get_401(api: Api) -> None:
    """Scenario: 로그인하지 않으면 조회도 변경도 401이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_logged_out(api)
    # When
    read = await when_read_alert_settings(api)
    write = await when_update_alert_settings(api, 7)
    # Then
    then_problem_is(read, status=401, type_suffix="unauthenticated")
    then_problem_is(write, status=401, type_suffix="unauthenticated")


@pytest.mark.parametrize("days", [1, 365])
async def test_the_bounds_are_accepted(api: Api, days: int) -> None:
    """Scenario: 경계값 1일과 365일은 저장된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_update_alert_settings(api, days)
    # Then
    then_status_is(response, 200)
    await then_stale_days_is(api, days)


@pytest.mark.parametrize("days", [0, 366, -1])
async def test_out_of_range_threshold_is_rejected_and_kept(api: Api, days: int) -> None:
    """Scenario: 범위 밖 값은 고정 문구의 422(invalid-value)이고 저장된 값은 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    assert (await when_update_alert_settings(api, 21)).status_code == 200
    # When
    response = await when_update_alert_settings(api, days)
    # Then
    then_range_is_rejected(response)
    await then_stale_days_is(api, 21)


@pytest.mark.parametrize("value", ["7", 7.5, True, None])
async def test_non_integer_threshold_is_rejected_by_the_request_schema(
    api: Api, value: object
) -> None:
    """Scenario: 문자열·소수·bool·null은 422(request-validation)이고 값은 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_update_alert_settings(api, value)
    # Then
    then_format_is_rejected(response)
    await then_stale_days_is(api, DEFAULT_STALE_DAYS)


@pytest.mark.parametrize("body", [{}, {"stale_days": 7, "long_stay_days": 30}])
async def test_missing_or_unknown_fields_are_rejected_by_the_request_schema(
    api: Api, body: dict[str, object]
) -> None:
    """Scenario: 필드 누락·알 수 없는 필드는 422(request-validation)이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_update_alert_settings_body(api, body)
    # Then
    then_format_is_rejected(response)
    await then_stale_days_is(api, DEFAULT_STALE_DAYS)


async def test_the_last_save_wins_and_replaces_the_saver(api: Api) -> None:
    """Scenario: 다른 admin이 다시 저장하면 값·저장자·시각이 모두 마지막 저장으로 바뀐다."""
    # Given
    await given_logged_in_as(api, role="admin")
    assert (await when_update_alert_settings(api, 7)).status_code == 200
    await given_logged_in_as(api, role="admin", login_id="boss2")
    api.clock.advance(300)
    # When
    response = await when_update_alert_settings(api, 30)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert body["stale_days"] == 30
    then_updated_by_is_user_ref(body, user_id=await current_user_id(api), name="사용자 boss2")
    then_updated_at_is_just_now(body)
    assert (await when_read_alert_settings(api)).json() == body


async def test_admin_who_saved_threshold_is_resigned_not_deleted(api: Api) -> None:
    """Scenario: 기준을 저장한 admin을 삭제하면 퇴사 처리되고 저장자가 퇴사로 표시된다."""
    # Given
    await given_logged_in_as(api, role="admin", login_id="boss2")
    assert (await when_update_alert_settings(api, 7)).status_code == 200
    await given_logged_in_as(api, role="admin")
    target_id = await id_of(api, "boss2")
    # When
    response = await when_delete_user(api, target_id)
    # Then
    then_status_is(response, 200)
    then_body_is(response, {"outcome": "resigned"})
    await then_user_is_listed_as_resigned(api, "boss2")
    saver = (await when_read_alert_settings(api)).json()["updated_by"]
    assert (saver["id"], saver["resigned"]) == (target_id, True)
