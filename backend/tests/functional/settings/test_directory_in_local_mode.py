"""Feature: 앱에서 계정을 직접 관리하는 시스템에서는 AD 설정을 저장하거나 시험할 수 없다."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_MODE_ONLY
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.local_accounts import given_local_admin_logged_in
from tests.functional.steps.settings import (
    probe_payload,
    update_payload,
    when_test_connection,
    when_update_settings,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_directory_settings_cannot_be_saved_in_local_mode(api: Api) -> None:
    """Scenario: local 모드에서 admin이 AD 설정을 저장하려 하면 409이고 AD에는 가지 않는다."""
    # Given
    await given_local_admin_logged_in(api)
    # When
    response = await when_update_settings(api, update_payload(expected_revision=None))
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == DIRECTORY_MODE_ONLY
    assert api.directory.discover_calls == []
    assert api.directory.authenticate_calls == []


async def test_directory_connection_test_is_rejected_in_local_mode(api: Api) -> None:
    """Scenario: local 모드에서 AD 연결 시험도 409이고 AD에는 가지 않는다."""
    # Given
    await given_local_admin_logged_in(api)
    # When
    response = await when_test_connection(api, probe_payload())
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert api.directory.discover_calls == []


async def test_storage_settings_stay_available_in_local_mode(api: Api) -> None:
    """Scenario: 저장 위치 설정은 local 모드에서도 그대로 조회된다."""
    # Given
    await given_local_admin_logged_in(api)
    # When
    response = await api.get("/api/v1/settings/storage")
    # Then
    then_status_is(response, 200)
