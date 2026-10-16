"""Feature: 로그인·최초 설정에 낸 비밀번호와 원본 아이디·IP는 DB 어디에도 저장되지 않는다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_setup_prerequisites_configured
from tests.functional.steps.login_db import then_no_secret_is_stored
from tests.functional.steps.setup import when_passwords_are_submitted_to_setup_and_login
from tests.support.auth_seed import DUMMY_PASSWORD

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_auth_flows_leave_no_password_in_any_table(api: Api) -> None:
    """Scenario: 최초 설정과 로그인(성공·실패) 뒤 인증 테이블에 비밀번호·원본 아이디·IP가 없다."""
    # Given
    wrong = DUMMY_PASSWORD + "-wrong"
    api.directory.add_account("kim", DUMMY_PASSWORD)
    await given_setup_prerequisites_configured(api)
    # When
    await when_passwords_are_submitted_to_setup_and_login(
        api, login_id="kim", correct=DUMMY_PASSWORD, wrong=wrong
    )
    # Then
    await then_no_secret_is_stored(api, secrets=[DUMMY_PASSWORD, wrong])
