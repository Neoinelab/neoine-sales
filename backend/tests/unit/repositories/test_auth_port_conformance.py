"""인증 Port를 Fake·실제 구현이 충족하는지 정적으로 검증한다.

AD 설정 개편(2026-10-29)으로 Port 3개(SecretCipher, PasswordHasher, UserPasswordHashRepository)가
늘었고 DirectoryAuthenticator·DirectorySettingsRepository 시그니처가 바뀌었다.
"""

import inspect
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.application.ports.directory_settings_repository import DirectorySettingsRepository
from app.application.ports.login_failure_repository import LoginFailureRepository
from app.application.ports.session_repository import SessionRepository
from app.application.ports.unit_of_work import UnitOfWork
from app.application.ports.user_password_hash_repository import UserPasswordHashRepository
from app.application.ports.user_repository import UserRepository
from app.infra.auth.ldap import LdapDirectoryAuthenticator
from app.infra.crypto.fernet_cipher import FernetSecretCipher
from app.infra.crypto.scrypt_hasher import ScryptPasswordHasher
from app.infra.db.directory_settings_repository import SqlDirectorySettingsRepository
from app.infra.db.login_failure_repository import SqlLoginFailureRepository
from app.infra.db.session_repository import SqlSessionRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.infra.db.user_password_hash_repository import SqlUserPasswordHashRepository
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
    from app.application.ports.directory import DirectoryAuthenticator
    from app.application.ports.password_hasher import PasswordHasher
    from app.application.ports.secret_cipher import SecretCipher

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
    """인증 Fake 저장소 네 개가 각 Port 타입을 충족한다."""
    # when: Fake 저장소를 각 Port 타입으로 받는다 (정적 타입 검사)
    users: UserRepository = FakeUserRepository()
    failures: LoginFailureRepository = FakeLoginFailureRepository()
    settings: DirectorySettingsRepository = FakeDirectorySettingsRepository()
    sessions: SessionRepository = FakeSessionRepository()

    # then: 모두 만들어진다
    assert None not in (users, failures, settings, sessions)


def test_fake_directory_authenticator_satisfies_the_port() -> None:
    """Fake 디렉터리 인증기가 DirectoryAuthenticator Port를 충족한다."""
    # when: Fake를 Port 타입으로 받는다 (정적 타입 검사)
    fake: DirectoryAuthenticator = FakeDirectoryAuthenticator()

    # then: 만들어진다
    assert fake is not None


def test_ldap_authenticator_satisfies_the_port() -> None:
    """LDAP 인증기가 DirectoryAuthenticator Port를 충족한다."""
    # when: 실제 구현을 Port 타입으로 받는다 (정적 타입 검사)
    real: DirectoryAuthenticator = LdapDirectoryAuthenticator()

    # then: 만들어진다
    assert real is not None


def test_ldap_authenticator_methods_are_coroutines() -> None:
    """LDAP 인증기의 인증·Base DN 탐색 메서드는 코루틴이고 예전 probe는 없다."""
    # when·then: authenticate·discover_base_dn은 코루틴이고 probe 속성은 Fake·실제 모두 없다
    assert inspect.iscoroutinefunction(LdapDirectoryAuthenticator.authenticate)
    assert inspect.iscoroutinefunction(LdapDirectoryAuthenticator.discover_base_dn)
    assert not hasattr(LdapDirectoryAuthenticator, "probe")  # discover_base_dn이 대체했다
    assert not hasattr(FakeDirectoryAuthenticator, "probe")


def test_fake_and_real_secret_ciphers_satisfy_the_port() -> None:
    """Fake와 실제 비밀 암호기가 SecretCipher Port를 충족하고 동기 호출이다."""
    # when: Fake와 Fernet 구현을 Port 타입으로 받는다 (정적 타입 검사)
    fake: SecretCipher = FakeSecretCipher()
    real: SecretCipher = FernetSecretCipher(SecretStr(Fernet.generate_key().decode()))

    # then: 둘 다 만들어지고 seal·unseal은 코루틴이 아니다
    assert None not in (fake, real)
    assert not inspect.iscoroutinefunction(FernetSecretCipher.seal)  # CPU가 작아 동기 호출이다
    assert not inspect.iscoroutinefunction(FernetSecretCipher.unseal)


def test_fake_and_real_password_hashers_satisfy_the_port() -> None:
    """Fake와 실제 해시기가 PasswordHasher Port를 충족하고 비동기 호출이다."""
    # when: Fake와 scrypt 구현을 Port 타입으로 받는다 (정적 타입 검사)
    fake: PasswordHasher = FakePasswordHasher()
    real: PasswordHasher = ScryptPasswordHasher()

    # then: 둘 다 만들어지고 hash·verify는 코루틴이다
    assert None not in (fake, real)
    assert inspect.iscoroutinefunction(ScryptPasswordHasher.hash)
    assert inspect.iscoroutinefunction(ScryptPasswordHasher.verify)


def test_password_hash_repositories_satisfy_the_port() -> None:
    """비밀번호 해시 저장소 Fake와 SQL 구현이 Port 메서드를 모두 가진다."""
    # when·then: get·save·delete가 Port, SQL 구현, Fake에 모두 있다
    fake: UserPasswordHashRepository = FakeUserPasswordHashRepository()
    for name in ("get", "save", "delete"):
        assert callable(getattr(SqlUserPasswordHashRepository, name))
        assert callable(getattr(fake, name))
        assert hasattr(UserPasswordHashRepository, name)


def test_sql_auth_repositories_expose_the_port_methods() -> None:
    """SQL 인증 저장소들이 Port 메서드를 모두 가지고 세션은 삭제 방식이다."""
    # when·then: 저장소 Port 메서드가 SQL 구현에 있고 세션 revoke 메서드는 없다
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
    """UnitOfWork Port와 구현들이 인증 저장소 속성을 노출한다."""
    # given: Fake UnitOfWork
    fake = FakeUnitOfWork()

    # when·then: 인증 저장소 속성 4개가 Port, Fake, SQL 구현에 모두 있다
    for name in ("users", "login_failures", "directory_settings", "password_hashes"):
        assert hasattr(UnitOfWork, name)
        assert hasattr(fake, name)
        assert name in SqlUnitOfWork.__annotations__


def test_auth_settings_repositories_satisfy_the_port() -> None:
    """인증 방식 설정 저장소 Fake와 SQL 구현이 Port를 충족한다."""
    from app.application.ports.auth_settings_repository import (  # noqa: PLC0415
        AuthSettingsRepository,
    )
    from app.infra.db.auth_settings_repository import SqlAuthSettingsRepository  # noqa: PLC0415
    from tests.fakes.auth_settings_repository import FakeAuthSettingsRepository  # noqa: PLC0415

    # when·then: get·save가 Port, SQL 구현, Fake에 있고 SQL 구현은 코루틴이다
    fake: AuthSettingsRepository = FakeAuthSettingsRepository()
    for name in ("get", "save"):
        assert callable(getattr(SqlAuthSettingsRepository, name))
        assert callable(getattr(fake, name))
        assert hasattr(AuthSettingsRepository, name)
        assert inspect.iscoroutinefunction(getattr(SqlAuthSettingsRepository, name))


def test_session_repository_port_and_implementations_have_delete_others_for_user() -> None:
    """세션 저장소 Port와 구현들이 delete_others_for_user를 가진다."""
    # when·then: Port에 있고 SQL·Fake 구현은 코루틴이다
    assert hasattr(SessionRepository, "delete_others_for_user")
    assert inspect.iscoroutinefunction(SqlSessionRepository.delete_others_for_user)
    assert inspect.iscoroutinefunction(FakeSessionRepository.delete_others_for_user)


def test_unit_of_work_port_and_implementations_expose_auth_settings() -> None:
    """UnitOfWork Port와 구현들이 auth_settings를 노출한다."""
    # when·then: Port, Fake, SQL 구현에 auth_settings가 있다
    assert hasattr(UnitOfWork, "auth_settings")
    assert hasattr(FakeUnitOfWork(), "auth_settings")
    assert "auth_settings" in SqlUnitOfWork.__annotations__
