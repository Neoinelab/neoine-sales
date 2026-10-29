"""인증 Port를 Fake·실제 구현이 충족하는지 정적으로 검증한다(T-P11).

AD 설정 개편(2026-10-29)으로 Port 3개(SecretCipher, PasswordHasher, UserPasswordHashRepository)가
늘었고 DirectoryAuthenticator·DirectorySettingsRepository 시그니처가 바뀌었다.
"""

import inspect
from typing import TYPE_CHECKING

from app.application.ports.user_password_hash_repository import UserPasswordHashRepository
from app.infra.crypto.fernet_cipher import FernetSecretCipher
from app.infra.crypto.scrypt_hasher import ScryptPasswordHasher
from app.infra.db.user_password_hash_repository import SqlUserPasswordHashRepository
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.application.ports.directory_settings_repository import DirectorySettingsRepository
from app.application.ports.login_failure_repository import LoginFailureRepository
from app.application.ports.session_repository import SessionRepository
from app.application.ports.unit_of_work import UnitOfWork
from app.application.ports.user_repository import UserRepository
from app.infra.auth.ldap import LdapDirectoryAuthenticator
from app.infra.db.directory_settings_repository import SqlDirectorySettingsRepository
from app.infra.db.login_failure_repository import SqlLoginFailureRepository
from app.infra.db.session_repository import SqlSessionRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.infra.db.user_repository import SqlUserRepository
from tests.fakes.directory import FakeDirectoryAuthenticator
from tests.fakes.directory_settings_repository import FakeDirectorySettingsRepository
from tests.fakes.password_hasher import FakePasswordHasher
from tests.fakes.secret_cipher import FakeSecretCipher
from tests.fakes.session_repository import FakeSessionRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.user_password_hashes import FakeUserPasswordHashRepository
from tests.fakes.user_repository import FakeLoginFailureRepository, FakeUserRepository

if TYPE_CHECKING:
    from app.application.ports.password_hasher import PasswordHasher
    from app.application.ports.secret_cipher import SecretCipher

    from app.application.ports.directory import DirectoryAuthenticator

USER_METHODS = (
    "add",
    "get",
    "get_for_update",
    "get_refs",
    "get_active_by_login_id",
    "list_users",
    "search_refs",
    "count_active_admins",
    "update",
    "delete",
    "has_links",
    "lock_assignable",
    "lock_roster",
)


def test_fake_auth_repositories_satisfy_their_ports() -> None:
    users: UserRepository = FakeUserRepository()
    failures: LoginFailureRepository = FakeLoginFailureRepository()
    settings: DirectorySettingsRepository = FakeDirectorySettingsRepository()
    sessions: SessionRepository = FakeSessionRepository()

    assert None not in (users, failures, settings, sessions)


def test_fake_directory_authenticator_satisfies_the_port() -> None:
    fake: DirectoryAuthenticator = FakeDirectoryAuthenticator()

    assert fake is not None


def test_ldap_authenticator_satisfies_the_port() -> None:
    real: DirectoryAuthenticator = LdapDirectoryAuthenticator()

    assert real is not None


def test_ldap_authenticator_methods_are_coroutines() -> None:
    assert inspect.iscoroutinefunction(LdapDirectoryAuthenticator.authenticate)
    assert inspect.iscoroutinefunction(LdapDirectoryAuthenticator.discover_base_dn)
    assert not hasattr(LdapDirectoryAuthenticator, "probe")  # discover_base_dn이 대체했다
    assert not hasattr(FakeDirectoryAuthenticator, "probe")


def test_fake_and_real_secret_ciphers_satisfy_the_port() -> None:
    fake: SecretCipher = FakeSecretCipher()
    real: SecretCipher = FernetSecretCipher(SecretStr(Fernet.generate_key().decode()))

    assert None not in (fake, real)
    assert not inspect.iscoroutinefunction(FernetSecretCipher.seal)  # CPU가 작아 동기 호출이다
    assert not inspect.iscoroutinefunction(FernetSecretCipher.unseal)


def test_fake_and_real_password_hashers_satisfy_the_port() -> None:
    fake: PasswordHasher = FakePasswordHasher()
    real: PasswordHasher = ScryptPasswordHasher()

    assert None not in (fake, real)
    assert inspect.iscoroutinefunction(ScryptPasswordHasher.hash)
    assert inspect.iscoroutinefunction(ScryptPasswordHasher.verify)


def test_password_hash_repositories_satisfy_the_port() -> None:
    fake: UserPasswordHashRepository = FakeUserPasswordHashRepository()
    for name in ("get", "save", "delete"):
        assert callable(getattr(SqlUserPasswordHashRepository, name))
        assert callable(getattr(fake, name))
        assert hasattr(UserPasswordHashRepository, name)


def test_sql_auth_repositories_expose_the_port_methods() -> None:
    for name in USER_METHODS:
        assert callable(getattr(SqlUserRepository, name))
        assert callable(getattr(FakeUserRepository, name))
        assert hasattr(UserRepository, name)
    for name in ("get_for_update", "save", "delete"):
        assert callable(getattr(SqlLoginFailureRepository, name))
        assert hasattr(LoginFailureRepository, name)
    for name in ("get", "save"):
        assert callable(getattr(SqlDirectorySettingsRepository, name))
        assert hasattr(DirectorySettingsRepository, name)
    assert callable(SqlSessionRepository.delete_all_for_user)
    assert hasattr(SessionRepository, "delete_all_for_user")
    assert not hasattr(SessionRepository, "revoke_all_for_subject")  # 세션은 폐기가 아니라 삭제한다


def test_unit_of_work_port_and_implementations_expose_the_new_repositories() -> None:
    fake = FakeUnitOfWork()

    for name in ("users", "login_failures", "directory_settings", "password_hashes"):
        assert hasattr(UnitOfWork, name)
        assert hasattr(fake, name)
        assert name in SqlUnitOfWork.__annotations__
