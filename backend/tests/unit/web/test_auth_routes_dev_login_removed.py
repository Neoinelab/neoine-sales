"""개발용 로그인 폐지(2026-11-03) 라우터 계약: 경로가 없고 설정 응답에 dev_login이 없다."""

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
    """폐지된 개발용 로그인 경로는 404이고 세션 쿠키를 만들지 않는다.

    테스트 코드: AU-064
    """
    # given: 인증 없이 접속한 클라이언트
    async with anonymous(FakeUseCases()) as http:
        # when: 역할을 담아 POST /auth/dev-login을 부르면
        response = await http.post(DEV_LOGIN, json={"role": role})

    # then: 404이고 쿠키가 없다
    assert response.status_code == 404
    assert "set-cookie" not in response.headers


async def test_auth_config_has_exactly_the_setup_keys() -> None:
    """인증 설정 응답은 로그인 없이 다섯 개 키뿐이다(dev_login 없음).

    테스트 코드: AU-062
    """
    # given: 인증 없이 접속한 클라이언트
    async with anonymous(FakeUseCases()) as http:
        # when: GET /auth/config를 부르면
        body = (await http.get(CONFIG)).json()

    # then: 키가 정확히 다섯이다
    assert set(body) == CONFIG_KEYS
