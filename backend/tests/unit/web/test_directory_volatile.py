import pytest

from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.local_account_http import anonymous, signed_in_as

CONNECTION = {
    "host": "dc1.corp.test",
    "port": 636,
    "security": "ssl",
    "user_filter": "(sAMAccountName={login_id})",
    "connect_timeout_seconds": 5,
}
TEST_INPUT = {**CONNECTION, "bind_account": "operator", "bind_password": "temporary-password"}


@pytest.mark.parametrize("setup", [False, True])
async def test_only_connection_test_accepts_credentials_and_save_uses_a_proof(
    *, setup: bool
) -> None:
    """초기 설정과 Admin 모두 테스트 계정 없이 접속 설정만 저장한다.

    테스트 코드: IN-087
    """
    # given: 새 AD 설정과 연결 테스트용 임시 자격증명
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    context = anonymous(use_cases) if setup else signed_in_as(use_cases, "boss", Role.ADMIN)
    endpoint = "/api/v1/auth/setup/directory" if setup else "/api/v1/settings/directory"
    async with context as http:
        tested = await http.post(f"{endpoint}/test", json=TEST_INPUT)
        assert tested.status_code == 200
        assert tested.json()["success"] is True
        assert await use_cases.uow.directory_settings.get() is None

        # when: 테스트 결과만 사용하여 설정을 저장한다
        body = {**CONNECTION, "test_token": tested.json()["test_token"]}
        if not setup:
            body["expected_revision"] = None
        saved = await http.put(endpoint, json=body)

        # then: 계정·비밀번호는 응답에 없으며 저장된 설정도 자격증명을 갖지 않는다
        assert saved.status_code == 200
        assert "bind_account" not in saved.json()
        assert "bind_credential_status" not in saved.json()
        assert "temporary-password" not in saved.text
        stored = await use_cases.uow.directory_settings.get()
        assert stored is not None
        assert stored.base_dn == tested.json()["base_dn"]


async def test_a_test_proof_cannot_save_different_connection_settings() -> None:
    """테스트 후 서버 주소를 바꾸면 재테스트 없이는 저장할 수 없다.

    테스트 코드: IN-087
    """
    # given: 초기 설정에서 원래 서버의 연결 테스트에 성공했다
    use_cases = FakeUseCases()
    async with anonymous(use_cases) as http:
        tested = await http.post("/api/v1/auth/setup/directory/test", json=TEST_INPUT)
        assert tested.status_code == 200

        # when: 다른 서버를 같은 성공 토큰으로 저장한다
        response = await http.put(
            "/api/v1/auth/setup/directory",
            json={
                **CONNECTION,
                "host": "other.corp.test",
                "test_token": tested.json()["test_token"],
            },
        )

        # then: 저장하지 않고 연결 테스트를 다시 요구한다
        assert response.status_code == 422
        assert await use_cases.uow.directory_settings.get() is None
