"""Feature: 운영자는 서버와 DB 상태를 확인할 수 있다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import (
    then_body_is,
    then_problem_is,
    then_response_does_not_mention,
    then_status_is,
)
from tests.functional.steps.health import (
    UNREACHABLE_DB_PASSWORD,
    given_database_unreachable,
    when_check_liveness,
    when_check_readiness,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_anonymous_operator_sees_the_server_is_alive(api: Api) -> None:
    """Scenario: 로그인하지 않은 운영자가 생존 확인을 요청하면 서버가 살아 있다고 답한다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await when_check_liveness(api)
    # Then
    then_status_is(response, 200)
    then_body_is(response, {"status": "ok"})


async def test_operator_sees_the_service_is_ready_when_the_database_answers(api: Api) -> None:
    """Scenario: DB가 응답하면 준비 확인이 ready를 돌려준다."""
    # Given
    await given_logged_in_as(api, role="admin")  # 실제 DB에 쓰기·읽기가 되는 상태
    # When
    response = await when_check_readiness(api)
    # Then
    then_status_is(response, 200)
    then_body_is(response, {"status": "ready"})


async def test_readiness_is_503_without_leaking_the_cause_when_the_database_is_down(
    api: Api,
) -> None:
    """Scenario: DB에 접속할 수 없으면 준비 확인이 503 Problem이고 원인(접속 정보)은 감춘다."""
    # Given
    await given_database_unreachable(api)
    # When
    response = await when_check_readiness(api)
    # Then
    then_problem_is(response, status=503, type_suffix="not-ready")
    then_response_does_not_mention(response, UNREACHABLE_DB_PASSWORD, "postgresql", "127.0.0.1")
