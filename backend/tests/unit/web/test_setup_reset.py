"""인증 설정 행이 없으면 기존 관리자를 유지하며 재설정한다."""

import pytest

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.local_account_http import CONFIG, SETUP_MODE, SETUP_STORAGE, anonymous


@pytest.mark.parametrize("mode", ["local", "ad"])
async def test_missing_auth_settings_reopens_setup_and_keeps_the_existing_admin(mode: str) -> None:
    """기존 관리자가 있어도 방식 행이 없으면 재설정하고 저장 위치 등록으로 완료한다.

    테스트 코드: SU-080
    """
    # given: 관리자와 AD·저장 위치가 남아 있지만 인증 방식 행은 없다
    use_cases = FakeUseCases()
    boss = await use_cases.seed_user("boss", Role.ADMIN)
    await use_cases.seed_directory()
    await use_cases.seed_storage()
    async with anonymous(use_cases) as http:
        before = (await http.get(CONFIG)).json()
        assert before["auth_mode"] is None
        assert before["needs_directory_setup"] is True
        assert before["needs_storage_setup"] is True

        # when: 방식을 선택하고 저장 위치를 다시 등록한다
        if mode == "local":
            selected = await http.put(SETUP_MODE, json={"mode": mode})
            assert selected.status_code == 204
        else:
            selected = await http.put(
                "/api/v1/auth/setup/directory",
                json={
                    "host": "dc1.corp.test",
                    "port": 636,
                    "security": "ssl",
                    "bind_account": "svc@corp.test",
                    "bind_password": "qa-service-password",
                    "user_filter": "(sAMAccountName={login_id})",
                    "connect_timeout_seconds": 5,
                },
            )
            assert selected.status_code == 200
        pending = (await http.get(CONFIG)).json()
        assert pending["needs_storage_setup"] is True
        saved = await http.put(SETUP_STORAGE, json={"path": "/data/restored"})

        # then: 관리자 등록 없이 완료되고 공개 설정 API는 다시 닫힌다
        assert saved.status_code == 200
        assert saved.json()["path"] == "/data/restored"
        persisted = await use_cases.uow.storage_settings.get()
        assert persisted is not None
        assert persisted.path.value == "/data/restored"
        after = (await http.get(CONFIG)).json()
        assert after["auth_mode"] == mode
        assert (
            after["needs_directory_setup"],
            after["needs_storage_setup"],
            after["needs_admin_setup"],
        ) == (False, False, False)
        preserved = await use_cases.uow.users.get(boss.id)
        assert preserved.role is Role.ADMIN
        assert preserved.login_id == boss.login_id
        closed = await http.put(SETUP_MODE, json={"mode": "local"})
        assert closed.status_code == 409
