"""인증 테스트의 준비 도우미: AD 설정·사용자 행·세션을 Fake/실제 UoW 어느 쪽에나 넣는다."""

import hashlib
import hmac
from typing import TYPE_CHECKING

from app.domain.auth.principal import Role
from tests.factories import NOW
from tests.factories_auth import BASE_DN, make_user
from tests.fakes.auth_stack import THROTTLE_SECRET

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.directory.settings import DirectorySettings, StoredDirectorySettings
    from app.domain.storage.settings import StoredStorageSettings
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
    uow_factory: UnitOfWorkFactory,
    settings: DirectorySettings | None = None,
    *,
    base_dn: str = BASE_DN,
    unreadable: bool = False,
) -> StoredDirectorySettings:
    """AD 설정을 저장소에 직접 넣는다. 비밀번호는 FakeSecretCipher로 봉인한다.

    unreadable=True면 Fake가 풀 수 없는 토큰(키가 바뀐 상황)으로 넣는다.
    새 Port의 Fake는 사용 시점에 가져온다(구현 전에도 이 모듈을 쓰는 다른 테스트가 수집된다).
    """
    from tests.factories_directory import make_directory_settings  # noqa: PLC0415
    from tests.fakes.secret_cipher import FakeSecretCipher, foreign_secret  # noqa: PLC0415

    given = settings or make_directory_settings()
    sealed = (
        foreign_secret() if unreadable else FakeSecretCipher().seal(given.bind_password.reveal())
    )
    async with uow_factory() as uow:
        stored = await uow.directory_settings.save(
            given.connection,
            sealed,
            base_dn,
            expected_revision=None,
            updated_by=None,
            now=NOW,
        )
        await uow.commit()
    return stored


async def seed_password_hash(uow_factory: UnitOfWorkFactory, user: User, password: str) -> None:
    """user가 AD 로그인에 성공한 적이 있는 상태(대체 로그인용 해시가 있는 상태)를 만든다.

    해시는 FakePasswordHasher 형식이다(Fake 스택에서만 쓴다).
    """
    from tests.fakes.password_hasher import fake_hash_of  # noqa: PLC0415

    async with uow_factory() as uow:
        await uow.password_hashes.save(user.id, fake_hash_of(password), NOW)
        await uow.commit()


async def seed_storage(
    uow_factory: UnitOfWorkFactory, path: str = "/data/neoine-sales/files"
) -> StoredStorageSettings:
    """파일 저장 위치(최초 설정 2단계를 마친 상태)를 저장소에 직접 넣는다."""
    from app.domain.storage.path import StoragePath  # noqa: PLC0415 - 저장 위치 구현 지연 import

    async with uow_factory() as uow:
        stored = await uow.storage_settings.save(StoragePath.parse(path), updated_by=None, now=NOW)
        await uow.commit()
    return stored


async def seed_setup_prerequisites(uow_factory: UnitOfWorkFactory) -> None:
    """최초 admin 지정 전 단계(AD 설정 + 저장 위치)를 모두 마친 상태."""
    await seed_directory(uow_factory)
    await seed_storage(uow_factory)


async def seed_user(  # noqa: PLR0913 - 시나리오 준비용 옵션
    uow_factory: UnitOfWorkFactory,
    login_id: str = "kim",
    role: Role = Role.SALES,
    *,
    deleted: bool = False,
    resigned: bool = False,
    now: datetime = NOW,
) -> User:
    """now는 created_at. 생성 순서를 단언하는 테스트는 사용자마다 다른 시각을 준다.

    deleted=True면 등록한 뒤 물리 삭제한다(연결이 없던 사용자가 이미 없는 상황의 재현).
    resigned=True면 등록한 뒤 퇴사 처리한다(행은 남고 세션은 지워진 상황의 재현).
    """
    user = make_user(login_id, role, now=now)
    async with uow_factory() as uow:
        await uow.users.add(user)
        if deleted:
            await uow.users.delete(user.id)
        if resigned:
            user.resign(now)
            await uow.users.update(user)
        await uow.commit()
    return user


async def active_admin_logins(uow_factory: UnitOfWorkFactory) -> list[str]:
    async with uow_factory() as uow:
        users = await uow.users.list_users(limit=100)
    return sorted(u.login_id.value for u in users if u.role is Role.ADMIN)
