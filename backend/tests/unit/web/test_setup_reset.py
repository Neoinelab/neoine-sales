"""인증 설정 행이 없으면 기존 관리자를 유지하며 재설정한다."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.local_account_http import (
    CONFIG,
    ME,
    SETUP,
    SETUP_MODE,
    SETUP_STORAGE,
    anonymous,
)

if TYPE_CHECKING:
    from httpx import AsyncClient

    from app.domain.user.entities import User


async def _select_mode(http: AsyncClient, mode: str) -> None:
    before = (await http.get(CONFIG)).json()
    assert before["auth_mode"] is None
    assert before["needs_directory_setup"] is True
    assert before["needs_storage_setup"] is True
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
    assert (await http.get(CONFIG)).json()["needs_storage_setup"] is True


async def _register_ad_account(
    http: AsyncClient, use_cases: FakeUseCases, existing: User | None
) -> None:
    rejected = await http.post(
        SETUP, json={"login_id": "ad-operator", "password": "wrong-password"}
    )
    assert rejected.status_code == 401
    assert (await http.get(CONFIG)).json()["needs_admin_setup"] is True
    registered = await http.post(
        SETUP, json={"login_id": "ad-operator", "password": "correct-ad-password"}
    )
    assert registered.status_code == 200
    user = await use_cases.uow.users.get_active_by_login_id(LoginId("ad-operator"))
    assert user is not None
    assert user.display_name == "AD 운영자"
    assert user.email == "operator@corp.test"
    assert user.role is (existing.role if existing is not None else Role.ADMIN)
    if existing is not None:
        assert user.id == existing.id
    assert (await http.get(ME)).json()["user_id"] == user.id
    assert (await http.get(CONFIG)).json()["needs_admin_setup"] is False


@pytest.mark.parametrize(
    ("mode", "existing_role"),
    [("local", None), ("ad", None), ("ad", Role.USER), ("ad", Role.ADMIN)],
)
async def test_missing_auth_settings_reopens_setup_and_keeps_the_existing_admin(
    mode: str, existing_role: Role | None
) -> None:
    """기존 관리자를 보존하고 AD 재설정에서는 인증한 계정을 등록한다.

    테스트 코드: SU-080, SU-081
    """
    # given: 기존 관리자와 AD·저장 위치는 있지만 인증 방식 행이 없다
    use_cases = FakeUseCases()
    boss = await use_cases.seed_user("boss", Role.ADMIN)
    existing = None
    if existing_role is not None:
        existing = await use_cases.seed_user("ad-operator", existing_role)
    use_cases.directory.add_account(
        "ad-operator", "correct-ad-password", display_name="AD 운영자", email="operator@corp.test"
    )
    await use_cases.seed_directory()
    await use_cases.seed_storage()
    async with anonymous(use_cases) as http:
        # when: 인증 방식과 저장 위치를 등록하고 AD 방식이면 AD 계정으로 인증한다
        await _select_mode(http, mode)
        saved = await http.put(SETUP_STORAGE, json={"path": "/data/restored"})

        # then: 기존 저장 위치를 갱신하고 AD 계정을 등록한 뒤 공개 설정을 닫는다
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
        ) == (False, False, mode == "ad")
        if mode == "ad":
            await _register_ad_account(http, use_cases, existing)
        preserved = await use_cases.uow.users.get(boss.id)
        assert preserved.role is Role.ADMIN
        assert preserved.login_id == boss.login_id
        closed = await http.put(SETUP_MODE, json={"mode": "local"})
        assert closed.status_code == 409
