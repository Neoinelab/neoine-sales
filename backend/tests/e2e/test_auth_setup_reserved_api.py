"""POST /auth/setup: 예약 dev 아이디는 첫 admin이 될 수 없다 (리뷰 Major 3).

사용자 등록 API와 같은 422 invalid-value이고, 세션 쿠키가 없으며 최초 설정은 열린 채 유지된다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.credentials import LoginId
from tests.e2e.conftest import SESSION_COOKIE
from tests.e2e.payloads_auth import CONFIG, SETUP, credentials, problem_type

if TYPE_CHECKING:
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases


@pytest.mark.parametrize("reserved", ["dev-admin", "dev-sales", "dev-user"])
async def test_setup_admin_with_a_reserved_dev_login_id_is_422_and_setup_stays_open(
    anonymous_client: AsyncClient, use_cases: FakeUseCases, reserved: str
) -> None:
    await use_cases.seed_directory()
    use_cases.directory.add_account(reserved, "pw-reserved")

    response = await anonymous_client.post(SETUP, json=credentials(reserved, "pw-reserved"))

    assert response.status_code == 422
    assert problem_type(response.json()) == "invalid-value"
    assert SESSION_COOKIE not in response.headers.get("set-cookie", "")
    assert await use_cases.uow.users.get_active_by_login_id(LoginId(reserved)) is None
    flags = (await anonymous_client.get(CONFIG)).json()
    assert (flags["needs_directory_setup"], flags["needs_admin_setup"]) == (False, True)


async def test_setup_with_a_normal_account_still_works_after_a_reserved_attempt(
    anonymous_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_directory()
    use_cases.directory.add_account("dev-admin", "pw-reserved")
    use_cases.directory.add_account("kim", "pw-kim")
    await anonymous_client.post(SETUP, json=credentials("dev-admin", "pw-reserved"))

    response = await anonymous_client.post(SETUP, json=credentials("kim", "pw-kim"))

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
