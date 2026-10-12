"""인증 테스트의 준비 도우미: AD 설정·사용자 행·세션을 Fake/실제 UoW 어느 쪽에나 넣는다."""

import hashlib
import hmac
from typing import TYPE_CHECKING

from app.domain.auth.principal import Role
from tests.factories import NOW
from tests.factories_auth import make_directory_settings, make_user
from tests.fakes.auth_stack import THROTTLE_SECRET

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.directory.settings import DirectorySettings, StoredDirectorySettings
    from app.domain.user.entities import User

DUMMY_PASSWORD = "S3cret-Dummy-pw!"  # noqa: S105 - 가짜 값. 로그·응답·DB 누출 검사에도 쓴다


def hmac_key(label: str, value: str, secret: str = THROTTLE_SECRET) -> str:
    """로그인 시도 제한 카운터 키 계약: HMAC-SHA256(secret, '<label>:<value>')의 hex(64자)."""
    return hmac.new(secret.encode(), f"{label}:{value}".encode(), hashlib.sha256).hexdigest()


def account_key(login_id: str, secret: str = THROTTLE_SECRET) -> str:
    return hmac_key("acct", login_id, secret)


def ip_key(client_ip: str, secret: str = THROTTLE_SECRET) -> str:
    return hmac_key("ip", client_ip, secret)


async def seed_directory(
    uow_factory: UnitOfWorkFactory, settings: DirectorySettings | None = None
) -> StoredDirectorySettings:
    async with uow_factory() as uow:
        stored = await uow.directory_settings.save(
            settings or make_directory_settings(),
            expected_revision=None,
            updated_by=None,
            now=NOW,
        )
        await uow.commit()
    return stored


async def seed_user(
    uow_factory: UnitOfWorkFactory,
    login_id: str = "kim",
    role: Role = Role.SALES,
    *,
    deleted: bool = False,
    now: datetime = NOW,
) -> User:
    """now는 created_at. 생성 순서를 단언하는 테스트는 사용자마다 다른 시각을 준다."""
    user = make_user(login_id, role, now=now)
    if deleted:
        user.soft_delete(NOW)
    async with uow_factory() as uow:
        await uow.users.add(user)
        await uow.commit()
    return user


async def active_admin_logins(uow_factory: UnitOfWorkFactory) -> list[str]:
    async with uow_factory() as uow:
        users = await uow.users.list_active(limit=100)
    return sorted(u.login_id.value for u in users if u.role is Role.ADMIN)
