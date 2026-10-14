"""새 Port 4개와 SessionRepository 확장을 Fake·SQL 구현이 충족하는지 정적으로 검증한다(T-P11)."""

import inspect
from typing import TYPE_CHECKING

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
from tests.fakes.session_repository import FakeSessionRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.user_repository import FakeLoginFailureRepository, FakeUserRepository

if TYPE_CHECKING:
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
    assert inspect.iscoroutinefunction(LdapDirectoryAuthenticator.probe)


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

    for name in ("users", "login_failures", "directory_settings"):
        assert hasattr(UnitOfWork, name)
        assert hasattr(fake, name)
        assert name in SqlUnitOfWork.__annotations__
