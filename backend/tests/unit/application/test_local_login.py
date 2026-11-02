"""LocalLogin·PasswordLogin: local 모드는 저장 해시로 인증한다 (AC-5).

없는 아이디·퇴사자·해시 없음·불일치는 모두 같은 LOGIN_FAILED이고 같은 비용(verify(None) 더미)을
쓰며, 실패는 기존 시도 제한(아이디 5회, IP 30회)에 센다. AD 어댑터는 한 번도 부르지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import LOGIN_FAILED
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError, TooManyAttemptsError
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from tests.factories import NOW
from tests.fakes.auth_stack import LOCK, MAX_PER_ACCOUNT, SESSION_TTL
from tests.support.auth_seed import (
    account_key,
    seed_auth_mode,
    seed_directory,
    seed_local_user,
    seed_user,
)

if TYPE_CHECKING:
    from app.application.auth.directory_login import LoginOutcome
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

IP = "10.0.0.1"
PW = "pw-kim-1234"  # 가짜 값


@pytest.fixture(autouse=True)
async def _local_mode(uow_factory: UnitOfWorkFactory) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)


async def _login(auth: AuthStack, login_id: str = "kim", password: str = PW) -> LoginOutcome:
    return await auth.password_login.execute(
        login_id=login_id, password=Password(password), client_ip=IP
    )


# ---- LocalLogin ----


async def test_local_login_with_right_password_returns_the_principal_and_records_login(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    user = await seed_local_user(uow_factory, "kim", PW, Role.SALES, display_name="김영업")

    principal = await auth.local_login.execute(LoginId("kim"), Password(PW))

    assert (principal.user_id, principal.subject, principal.role) == (user.id, "kim", Role.SALES)
    assert (await uow.users.get(user.id)).last_login_at == NOW


async def test_local_login_keeps_the_stored_profile(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """AD 로그인과 달리 이름·이메일·전화를 덮어쓰지 않는다."""
    user = await seed_local_user(
        uow_factory, "kim", PW, display_name="김영업", email="kim@corp.test", phone="010-1234-5678"
    )

    await auth.local_login.execute(LoginId("kim"), Password(PW))

    stored = await uow.users.get(user.id)
    assert (stored.display_name, stored.email, stored.phone) == (
        "김영업",
        "kim@corp.test",
        "010-1234-5678",
    )


async def test_local_login_wrong_password_is_login_failed_and_does_not_record_login(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    user = await seed_local_user(uow_factory, "kim", PW)

    with pytest.raises(AuthenticationError) as caught:
        await auth.local_login.execute(LoginId("kim"), Password("wrong-password"))

    assert str(caught.value) == LOGIN_FAILED
    assert (await uow.users.get(user.id)).last_login_at is None


async def test_local_login_unknown_id_verifies_dummy_and_fails_alike(auth: AuthStack) -> None:
    with pytest.raises(AuthenticationError) as caught:
        await auth.local_login.execute(LoginId("ghost"), Password(PW))

    assert str(caught.value) == LOGIN_FAILED
    assert auth.hasher.verify_calls == [None]


async def test_local_login_resigned_user_fails_with_the_same_cost(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_local_user(uow_factory, "gone", PW, resigned=True)

    with pytest.raises(AuthenticationError) as caught:
        await auth.local_login.execute(LoginId("gone"), Password(PW))

    assert str(caught.value) == LOGIN_FAILED
    assert auth.hasher.verify_calls == [None]


async def test_local_login_without_hash_fails_with_the_same_cost(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_local_user(uow_factory, "kim", PW, with_hash=False)

    with pytest.raises(AuthenticationError) as caught:
        await auth.local_login.execute(LoginId("kim"), Password(PW))

    assert str(caught.value) == LOGIN_FAILED
    assert auth.hasher.verify_calls == [None]


async def test_local_login_ambiguous_login_id_fails(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_local_user(uow_factory, "kim", PW)
    await seed_user(uow_factory, "kim", Role.SALES)  # 재직 행이 둘이 된 정합 위반

    with pytest.raises(AuthenticationError) as caught:
        await auth.local_login.execute(LoginId("kim"), Password(PW))

    assert str(caught.value) == LOGIN_FAILED


async def test_local_login_verifies_outside_any_transaction(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_local_user(uow_factory, "kim", PW)
    auth.hasher.open_units_probe = lambda: uow.open_units

    await auth.local_login.execute(LoginId("kim"), Password(PW))

    assert auth.hasher.open_units_at_verify == [0]


# ---- PasswordLogin ----


async def test_password_login_in_local_mode_issues_a_session_without_a_warning(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_local_user(uow_factory, "kim", PW, Role.ADMIN, display_name="김관리")

    outcome = await _login(auth)

    assert outcome.directory_warning is None
    assert outcome.session.expires_at == NOW + SESSION_TTL
    assert (await auth.authenticate.execute(outcome.session.token)).subject == "kim"


async def test_password_login_in_local_mode_never_calls_directory(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)  # 남아 있는 AD 설정이 있어도 쓰지 않는다
    await seed_local_user(uow_factory, "kim", PW)

    await _login(auth)
    with pytest.raises(AuthenticationError):
        await _login(auth, password="wrong-password")  # noqa: S106

    assert auth.directory.authenticate_calls == []
    assert auth.directory.discover_calls == []


async def test_password_login_wrong_password_counts_one_failure(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_local_user(uow_factory, "kim", PW)

    with pytest.raises(AuthenticationError) as caught:
        await _login(auth, password="wrong-password")  # noqa: S106

    assert str(caught.value) == LOGIN_FAILED
    assert uow.login_failures._items[account_key("kim")].failures == 1


async def test_password_login_unknown_id_counts_and_fails_alike(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    with pytest.raises(AuthenticationError) as caught:
        await _login(auth, "ghost")

    assert str(caught.value) == LOGIN_FAILED
    assert uow.login_failures._items[account_key("ghost")].failures == 1


async def test_password_login_success_clears_the_account_counter(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_local_user(uow_factory, "kim", PW)
    with pytest.raises(AuthenticationError):
        await _login(auth, password="wrong-password")  # noqa: S106

    await _login(auth)

    assert account_key("kim") not in uow.login_failures._items


async def test_password_login_locked_account_is_429_without_verifying(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_local_user(uow_factory, "kim", PW)
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(AuthenticationError):
            await _login(auth, password="wrong-password")  # noqa: S106
    verified = len(auth.hasher.verify_calls)

    with pytest.raises(TooManyAttemptsError):
        await _login(auth)  # 올바른 비밀번호여도 잠겨 있다

    assert len(auth.hasher.verify_calls) == verified


async def test_password_login_lock_ends_after_the_lock_duration(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    await seed_local_user(uow_factory, "kim", PW)
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(AuthenticationError):
            await _login(auth, password="wrong-password")  # noqa: S106
    clock.advance(LOCK.total_seconds())

    outcome = await _login(auth)

    assert outcome.session.principal.subject == "kim"


# ---- 방식에 따른 분기 ----


async def test_password_login_without_mode_row_and_admin_uses_directory(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """방식 행이 없는 기존 시스템(admin이 있음)은 AD 로그인이다 (AC-14)."""
    uow.auth_settings._items.clear()
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.ADMIN)

    outcome = await _login(auth, "kim", "pw-kim")

    assert outcome.session.principal.subject == "kim"
    assert len(auth.directory.authenticate_calls) == 1


async def test_password_login_in_ad_mode_still_uses_the_directory(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)

    await _login(auth, "kim", "pw-kim")

    assert len(auth.directory.authenticate_calls) == 1


async def test_password_login_in_ad_mode_rejects_a_local_style_hash_when_the_directory_answers(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """AD가 응답해 비밀번호를 거절하면 저장 해시가 맞아도 거부한다(기존 규칙 그대로)."""
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)
    await seed_local_user(uow_factory, "kim", "stored-pass-1")

    with pytest.raises(AuthenticationError):
        await _login(auth, "kim", "stored-pass-1")
