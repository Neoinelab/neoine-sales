"""Feature: admin은 저장된 AD 연결 설정을 조회할 수 있다(비밀번호는 보이지 않는다)."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import directory_payload, given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.platform import then_problem_kind_is
from tests.functional.steps.settings import (
    SETTINGS_FIELDS,
    STORED_DN,
    given_settings_row_removed,
    then_updated_at_is_just_now,
    when_read_settings,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_admin_reads_the_current_settings(api: Api) -> None:
    """Scenario: admin이 설정을 조회하면 저장된 연결 설정과 개정 번호가 나오고 비밀 값은 없다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_read_settings(api)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert set(body) == SETTINGS_FIELDS
    expected = directory_payload()
    assert {k: v for k, v in body.items() if k in expected} == expected
    assert body["base_dn"] == STORED_DN
    assert (body["revision"], body["updated_by"]) == (1, None)
    then_updated_at_is_just_now(body)
    assert not any("password" in key.lower() or "secret" in key.lower() for key in body)


async def test_reading_settings_before_any_are_saved_is_404(api: Api) -> None:
    """Scenario: 저장된 설정이 없으면 조회는 404 Problem(not-found)이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_settings_row_removed(api)
    # When
    response = await when_read_settings(api)
    # Then
    then_problem_kind_is(response, status=404, kinds=("not-found",))
