"""Feature: 예약된 개발용 아이디(dev-*)는 최초 admin이 될 수 없고 설정은 열린 채 유지된다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_ad_account, given_setup_prerequisites_configured
from tests.functional.steps.common import then_problem_is
from tests.functional.steps.login import (
    then_auth_flags_are,
    then_no_cookie_is_set,
    then_signed_in_as,
)
from tests.functional.steps.setup import (
    given_reserved_id_was_rejected,
    then_user_is_not_registered,
    when_set_up_admin,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("reserved", ["dev-admin", "dev-sales", "dev-user"])
async def test_setup_admin_with_a_reserved_dev_login_id_is_422_and_setup_stays_open(
    api: Api, reserved: str
) -> None:
    """Scenario: 예약된 dev 아이디로 최초 admin을 지정하면 422이고 설정은 열려 있다."""
    # Given
    await given_setup_prerequisites_configured(api)
    given_ad_account(api, login_id=reserved)
    # When
    response = await when_set_up_admin(api, login_id=reserved)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_no_cookie_is_set(response)
    await then_user_is_not_registered(api, login_id=reserved)
    await then_auth_flags_are(api, needs_directory=False, needs_storage=False, needs_admin=True)


async def test_setup_with_a_normal_account_still_works_after_a_reserved_attempt(api: Api) -> None:
    """Scenario: 예약 아이디 시도가 거절된 뒤에도 일반 계정으로 최초 설정을 마칠 수 있다."""
    # Given
    await given_setup_prerequisites_configured(api)
    await given_reserved_id_was_rejected(api, login_id="dev-admin")
    given_ad_account(api, login_id="kim")
    # When
    response = await when_set_up_admin(api, login_id="kim")
    # Then
    then_signed_in_as(response, subject="kim", email=None, name="kim", role="admin")
