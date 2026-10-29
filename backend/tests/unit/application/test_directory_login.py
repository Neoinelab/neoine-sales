"""DirectoryLogin 유스케이스: 서비스 계정 search-then-bind 로그인과 비밀번호 해시 저장(AC7·AC13).

AD가 답하지 못할 때의 대체 로그인은 test_directory_login_fallback.py다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_NOT_CONFIGURED, LOGIN_FAILED
from app.application.ports.directory import InvalidCredentialsError, VerificationStage
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.factories import NOW
from tests.factories_auth import BASE_DN, BIND_PASSWORD
from tests.factories_directory import make_directory_connection
from tests.fakes.auth_stack import SESSION_TTL
from tests.support.auth_seed import DUMMY_PASSWORD, account_key, seed_directory, seed_user

if TYPE_CHECKING:
    from app.application.auth.issue_session import IssuedSession
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.entities import User
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.directory import FakeDirectoryAuthenticator
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

IP = "10.0.0.1"


@pytest.fixture
async def ready(uow_factory: UnitOfWorkFactory) -> None:
    """AD 설정이 있고 kim(sales)이 등록된 상태."""
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)


async def _login(
    auth: AuthStack,
    login_id: str = "kim",
    password: str = "pw-kim",  # noqa: S107
) -> IssuedSession:
    outcome = await auth.login.execute(login_id=login_id, password=Password(password), client_ip=IP)
    return outcome.session


@pytest.mark.usefixtures("ready")
async def test_login_issues_session_for_registered_user(auth: AuthStack, clock: FixedClock) -> None:
    issued = (
        await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)
    ).session

    assert issued.principal.subject == "kim"
    assert issued.principal.role is Role.SALES
    assert issued.expires_at == NOW + SESSION_TTL
    assert (await auth.authenticate.execute(issued.token)).subject == "kim"


@pytest.mark.usefixtures("ready")
async def test_login_principal_carries_the_users_row_id(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    issued = await _login(auth)

    stored = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert stored is not None
    assert issued.principal.user_id == stored.id


@pytest.mark.usefixtures("ready")
async def test_login_after_reregistration_uses_the_new_row_not_the_resigned_one(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    old = await seed_user(uow_factory, "lee", Role.USER, resigned=True)
    new = await seed_user(uow_factory, "lee", Role.SALES)
    auth.directory.add_account("lee", "pw-lee")

    issued = (
        await auth.login.execute(login_id="lee", password=Password("pw-lee"), client_ip=IP)
    ).session

    assert issued.principal.user_id == new.id
    assert issued.principal.user_id != old.id
    assert issued.principal.role is Role.SALES
    assert (await uow.users.get(old.id)).last_login_at is None  # 퇴사 행은 건드리지 않는다


@pytest.mark.usefixtures("ready")
async def test_login_role_comes_from_the_users_table(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "lee", Role.USER)
    auth.directory.add_account("lee", "pw-lee")

    issued = (
        await auth.login.execute(login_id="lee", password=Password("pw-lee"), client_ip=IP)
    ).session

    assert issued.principal.role is Role.USER


@pytest.mark.usefixtures("ready")
async def test_login_succeeds_when_the_directory_display_name_is_256_chars(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    directory.add_account("kim", "pw-kim", display_name="가" * 256, email="kim@corp.test")

    issued = await _login(auth)

    assert issued.principal.subject == "kim"
    assert (await auth.authenticate.execute(issued.token)).subject == "kim"


@pytest.mark.usefixtures("ready")
async def test_login_updates_last_login_and_profile(auth: AuthStack, uow: FakeUnitOfWork) -> None:
    await _login(auth)

    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.last_login_at == NOW
    assert user.display_name == "김영업"
    assert user.email == "kim@corp.test"


@pytest.mark.usefixtures("ready")
async def test_login_overwrites_profile_with_the_latest_directory_values(
    auth: AuthStack, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    await _login(auth)
    clock.advance(3600)
    auth.directory.add_account("kim", "pw-kim", display_name="김부장", email="kim2@corp.test")

    await _login(auth)

    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert (user.display_name, user.email) == ("김부장", "kim2@corp.test")
    assert user.last_login_at == clock.now()


@pytest.mark.usefixtures("ready")
@pytest.mark.parametrize(
    "case",
    [
        "wrong-password",
        "unknown-in-directory",
        "not-registered",
        "deleted",
        "resigned",
        "malformed-id",
    ],
)
async def test_login_failures_share_one_message_and_issue_no_session(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, case: str
) -> None:
    auth.directory.add_account("newbie", "pw-newbie")  # AD에는 있지만 앱에 등록되지 않음
    auth.directory.add_account("gone", "pw-gone")
    auth.directory.add_account("quit", "pw-quit")  # AD에는 있지만 앱에서 퇴사 처리됨
    await seed_user(uow_factory, "gone", Role.SALES, deleted=True)
    await seed_user(uow_factory, "quit", Role.SALES, resigned=True)
    attempts = {
        "wrong-password": ("kim", "not-the-password"),
        "unknown-in-directory": ("ghost", "pw-ghost"),
        "not-registered": ("newbie", "pw-newbie"),
        "deleted": ("gone", "pw-gone"),
        "resigned": ("quit", "pw-quit"),
        "malformed-id": ("kim)(uid=*", "pw-kim"),
    }
    login_id, password = attempts[case]

    with pytest.raises(AuthenticationError) as caught:
        await _login(auth, login_id, password)

    assert type(caught.value) is AuthenticationError
    assert str(caught.value) == LOGIN_FAILED
    assert uow.sessions._items == {}


@pytest.mark.usefixtures("ready")
async def test_login_failure_exception_never_contains_the_password(auth: AuthStack) -> None:
    with pytest.raises(AuthenticationError) as caught:
        await _login(auth, "kim", DUMMY_PASSWORD)

    chain = [caught.value, caught.value.__cause__, caught.value.__context__]
    for error in filter(None, chain):
        assert DUMMY_PASSWORD not in f"{error!s}{error!r}{error.args!r}"


@pytest.mark.usefixtures("ready")
async def test_login_id_is_normalized_before_lookup(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    issued = (
        await auth.login.execute(login_id="  Kim ", password=Password("pw-kim"), client_ip=IP)
    ).session

    assert issued.principal.subject == "kim"
    assert [call.login_id for call in directory.authenticate_calls] == [LoginId("kim")]


async def test_login_without_directory_settings_and_without_a_hash_is_rejected_and_counted(
    auth: AuthStack, directory: FakeDirectoryAuthenticator, uow: FakeUnitOfWork
) -> None:
    """설정이 없으면 AD를 부르지 않고 대체 로그인으로 넘어가며, 해시가 없으면 실패 1회다(AC14)."""
    with pytest.raises(InvalidStateError) as caught:
        await _login(auth)

    assert str(caught.value) == DIRECTORY_NOT_CONFIGURED
    assert directory.authenticate_calls == []
    assert directory.discover_calls == []
    assert uow.login_failures._items[account_key("kim")].failures == 1


@pytest.mark.usefixtures("ready")
async def test_login_passes_stored_base_dn_and_unsealed_password(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    await _login(auth)

    (call,) = directory.authenticate_calls
    assert call.base_dn == BASE_DN  # 로그인마다 다시 찾지 않고 저장된 값을 쓴다
    assert directory.discover_calls == []
    assert call.settings.connection == make_directory_connection()
    assert call.settings.bind_password.reveal() == BIND_PASSWORD  # 암호문을 풀어 쓴다
    assert call.login_id == LoginId("kim")
    assert call.password == "pw-kim"  # noqa: S105 - 가짜 값


@pytest.mark.usefixtures("ready")
async def test_login_uses_the_current_settings_each_time(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, directory: FakeDirectoryAuthenticator
) -> None:
    await _login(auth)
    async with uow_factory() as uow:
        await uow.directory_settings.save(
            make_directory_connection(host="dc2.corp.test"),
            auth.cipher.seal("Rotated-pw-9!"),
            "dc=other,dc=test",
            expected_revision=1,
            updated_by=None,
            now=NOW,
        )
        await uow.commit()

    await _login(auth)

    first, second = directory.authenticate_calls
    assert first.base_dn == BASE_DN
    assert (second.base_dn, second.settings.connection.host) == (
        "dc=other,dc=test",
        "dc2.corp.test",
    )
    assert second.settings.bind_password.reveal() == "Rotated-pw-9!"


@pytest.mark.usefixtures("ready")
async def test_login_passes_the_password_only_to_the_directory(
    auth: AuthStack, directory: FakeDirectoryAuthenticator, uow: FakeUnitOfWork
) -> None:
    directory.add_account("kim", DUMMY_PASSWORD)

    issued = await _login(auth, "kim", DUMMY_PASSWORD)

    assert directory.authenticate_calls[0].password == DUMMY_PASSWORD
    stored = repr(uow.users._items) + repr(uow.sessions._items) + repr(uow.login_failures._items)
    assert DUMMY_PASSWORD not in stored
    assert DUMMY_PASSWORD not in repr(issued)


@pytest.mark.usefixtures("ready")
async def test_login_of_a_user_deleted_during_the_login_is_a_plain_login_failure(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """읽은 직후 삭제가 끼어들어도 update의 NotFound(404)가 아니라 로그인 실패(401)가 된다."""
    original_get = uow.users.get_active_by_login_id

    async def get_then_delete(login_id: LoginId) -> User | None:
        found = await original_get(login_id)
        assert found is not None
        await uow.users.delete(found.id)  # 다른 요청이 사용자를 삭제하고 커밋했다
        return found

    uow.users.get_active_by_login_id = get_then_delete  # type: ignore[method-assign]

    with pytest.raises(AuthenticationError) as caught:
        await _login(auth)

    assert type(caught.value) is AuthenticationError
    assert str(caught.value) == LOGIN_FAILED
    assert uow.sessions._items == {}


@pytest.mark.usefixtures("ready")
async def test_successful_directory_login_saves_new_password_hash(
    auth: AuthStack, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    await _login(auth)

    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    first = await uow.password_hashes.get(user.id)
    assert first is not None
    assert await auth.hasher.verify(Password("pw-kim"), first)
    assert "pw-kim" not in repr(first)
    assert "pw-kim" not in first.encoded
    assert uow.password_hashes.saved_at(user.id) == NOW

    clock.advance(60)
    await _login(auth)

    second = await uow.password_hashes.get(user.id)
    assert second is not None
    assert second != first  # 새 솔트로 덮어쓴다
    assert uow.password_hashes.saved_at(user.id) == clock.now()
    assert len(uow.password_hashes._items) == 1


@pytest.mark.usefixtures("ready")
async def test_hash_follows_the_latest_directory_password(
    auth: AuthStack, directory: FakeDirectoryAuthenticator, uow: FakeUnitOfWork
) -> None:
    await _login(auth)
    directory.add_account("kim", "pw-kim-changed", display_name="김영업", email="kim@corp.test")

    await _login(auth, "kim", "pw-kim-changed")

    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    stored = await uow.password_hashes.get(user.id)
    assert stored is not None
    assert await auth.hasher.verify(Password("pw-kim-changed"), stored)
    assert not await auth.hasher.verify(Password("pw-kim"), stored)


@pytest.mark.usefixtures("ready")
@pytest.mark.parametrize("stage", [VerificationStage.BIND, VerificationStage.SEARCH])
async def test_rejected_password_gets_401_even_when_hash_matches(
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
    uow: FakeUnitOfWork,
    stage: VerificationStage,
) -> None:
    await _login(auth)  # 해시가 생긴다
    directory.authenticate_fails_with = InvalidCredentialsError(stage=stage)
    saved = dict(uow.password_hashes._items)
    verify_calls = len(auth.hasher.verify_calls)

    with pytest.raises(AuthenticationError) as caught:
        await _login(auth)  # 같은 비밀번호(해시와 일치)

    assert type(caught.value) is AuthenticationError
    assert str(caught.value) == LOGIN_FAILED
    assert uow.password_hashes._items == saved  # AD가 거부해도 해시는 지우지 않는다
    assert len(auth.hasher.verify_calls) == verify_calls  # 대체 로그인을 시도하지 않았다
    assert uow.login_failures._items[account_key("kim")].failures == 1


@pytest.mark.usefixtures("ready")
async def test_failed_directory_login_saves_no_hash(auth: AuthStack, uow: FakeUnitOfWork) -> None:
    with pytest.raises(AuthenticationError):
        await _login(auth, "kim", "not-the-password")

    assert uow.password_hashes._items == {}
    assert auth.hasher.hash_calls == 0


async def test_login_of_an_unregistered_user_saves_no_hash(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_directory(uow_factory)
    auth.directory.add_account("newbie", "pw-newbie")

    with pytest.raises(AuthenticationError):
        await _login(auth, "newbie", "pw-newbie")

    assert uow.password_hashes._items == {}


@pytest.mark.usefixtures("ready")
async def test_a_directory_login_carries_no_directory_warning(auth: AuthStack) -> None:
    outcome = await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    assert outcome.directory_warning is None


@pytest.mark.usefixtures("ready")
async def test_login_password_never_reaches_stored_rows_in_plain_text(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    await _login(auth, "kim", "pw-kim")

    stored = repr(uow.password_hashes._items) + repr(uow.directory_settings._items)
    assert "pw-kim" not in stored
    assert BIND_PASSWORD not in stored
