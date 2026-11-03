"""개발용 로그인 폐지(2026-11-03) 라우터 계약 (AC-1·2): 경로가 없고 설정 응답에 dev_login이 없다."""

import pytest

from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.local_account_http import CONFIG, anonymous

DEV_LOGIN = "/api/v1/auth/dev-login"
CONFIG_KEYS = {
    "directory_login",
    "needs_directory_setup",
    "needs_storage_setup",
    "needs_admin_setup",
    "auth_mode",
}


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_post_dev_login_is_not_found(role: str) -> None:
    async with anonymous(FakeUseCases()) as http:
        response = await http.post(DEV_LOGIN, json={"role": role})

    assert response.status_code == 404
    assert "set-cookie" not in response.headers


async def test_auth_config_has_exactly_the_setup_keys() -> None:
    async with anonymous(FakeUseCases()) as http:
        body = (await http.get(CONFIG)).json()

    assert set(body) == CONFIG_KEYS
