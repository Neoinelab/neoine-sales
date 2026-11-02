"""ChangeMyPassword: local 사용자가 현재 비밀번호를 확인하고 자기 비밀번호를 바꾼다 (AC-11).

현재 비밀번호 확인은 로그인과 같은 시도 제한을 공유한다.
틀리면 실패 1회, 잠기면 TooManyAttemptsError다.
성공하면 지금 세션은 두고 그 사용자의 다른 세션만 끝낸다. ad 모드·dev 사용자는 InvalidStateError.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import LOCAL_MODE_ONLY
from app.application.auth.tokens import hash_token
from app.domain.auth.credentials import Password
from app.domain.auth.errors import (
    TooManyAttemptsError,
    WeakPasswordError,
    WrongCurrentPasswordError,
)
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError, InvalidValueError
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.fakes.password_hasher import fake_hash_of
from tests.support.admin_seed import session_is_active
from tests.support.auth_seed import account_key, seed_auth_mode, seed_local_user

if TYPE_CHECKING:
    from app.application.auth.issue_session import IssuedSession
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

IP = "10.0.0.1"
OLD = "old-password-1"  # 가짜 값
NEW = "New-passw0rd"  # 가짜 값


class Me:
    """local 모드의 kim과 그 사용자의 세션 3개(첫 번째가 '지금' 쓰는 세션)."""

    def __init__(self, actor: Principal, sessions: list[IssuedSession]) -> None:
        self.actor = actor
        self.current, self.other_a, self.other_b = sessions


@pytest.fixture
async def me(auth: AuthStack, uow_factory: UnitOfWorkFactory) -> Me:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await seed_local_user(uow_factory, "kim", OLD, display_name="김영업")
    sessions = [await auth.issue.execute(kim.to_principal()) for _ in range(3)]
    return Me(kim.to_principal(), sessions)


async def _change(
    auth: AuthStack, me: Me, *, current: str = OLD, new: str = NEW, token: str | None = None
) -> None:
    await auth.change_my_password.execute(
        actor=me.actor,
        current=Password(current),
        new=Password(new),
        session_token=token or me.current.token,
        client_ip=IP,
    )


async def test_change_my_password_success_keeps_current_session_and_ends_others(
    auth: AuthStack, me: Me, uow_factory: UnitOfWorkFactory
) -> None:
    await _change(auth, me)

    assert await session_is_active(uow_factory, me.current.token)
    assert not await session_is_active(uow_factory, me.other_a.token)
    assert not await session_is_active(uow_factory, me.other_b.token)
    assert (await auth.authenticate.execute(me.current.token)).subject == "kim"


async def test_change_my_password_does_not_touch_other_users_sessions(
    auth: AuthStack, me: Me, uow_factory: UnitOfWorkFactory
) -> None:
    lee = await seed_local_user(uow_factory, "lee", "lee-password-1")
    lee_session = await auth.issue.execute(lee.to_principal())

    await _change(auth, me)

    assert await session_is_active(uow_factory, lee_session.token)


async def test_change_my_password_new_password_signs_in_and_old_does_not(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork
) -> None:
    await _change(auth, me)

    stored = await uow.password_hashes.get(me.actor.user_id)
    assert stored is not None
    assert await auth.hasher.verify(Password(NEW), stored) is True
    assert await auth.hasher.verify(Password(OLD), stored) is False


async def test_change_my_password_success_clears_the_account_counter(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork
) -> None:
    with pytest.raises(WrongCurrentPasswordError):
        await _change(auth, me, current="wrong-password")
    assert uow.login_failures._items[account_key("kim")].failures == 1

    await _change(auth, me)

    assert account_key("kim") not in uow.login_failures._items


async def test_change_my_password_wrong_current_is_invalid_value_and_counted(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    with pytest.raises(WrongCurrentPasswordError) as caught:
        await _change(auth, me, current="wrong-password")

    assert isinstance(caught.value, InvalidValueError)
    assert str(caught.value) == "현재 비밀번호가 올바르지 않습니다."
    assert uow.login_failures._items[account_key("kim")].failures == 1
    assert await uow.password_hashes.get(me.actor.user_id) == fake_hash_of(OLD)
    assert await session_is_active(uow_factory, me.other_a.token)  # 실패하면 세션은 그대로


async def test_change_my_password_locked_is_too_many_attempts_without_verifying(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork
) -> None:
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(WrongCurrentPasswordError):
            await _change(auth, me, current="wrong-password")
    verified = len(auth.hasher.verify_calls)

    with pytest.raises(TooManyAttemptsError):
        await _change(auth, me)  # 올바른 현재 비밀번호여도 잠겨 있다

    assert len(auth.hasher.verify_calls) == verified
    assert await uow.password_hashes.get(me.actor.user_id) == fake_hash_of(OLD)


async def test_change_my_password_failures_are_shared_with_login(auth: AuthStack, me: Me) -> None:
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(WrongCurrentPasswordError):
            await _change(auth, me, current="wrong-password")

    with pytest.raises(TooManyAttemptsError):
        await auth.password_login.execute(login_id="kim", password=Password(OLD), client_ip=IP)


@pytest.mark.parametrize("new", ["short7!", "1234567", "kim"])
async def test_change_my_password_weak_new_password_is_invalid_value_and_not_counted(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork, new: str
) -> None:
    with pytest.raises(WeakPasswordError) as caught:
        await _change(auth, me, new=new)

    assert not isinstance(caught.value, WrongCurrentPasswordError)
    assert uow.login_failures._items == {}
    assert await uow.password_hashes.get(me.actor.user_id) == fake_hash_of(OLD)


async def test_change_my_password_new_equal_to_login_id_is_invalid_value(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await seed_local_user(uow_factory, "kim.lee1", OLD)
    issued = await auth.issue.execute(kim.to_principal())

    with pytest.raises(InvalidValueError):
        await auth.change_my_password.execute(
            actor=kim.to_principal(),
            current=Password(OLD),
            new=Password("Kim.Lee1"),
            session_token=issued.token,
            client_ip=IP,
        )


async def test_change_my_password_in_ad_mode_is_invalid_state(
    auth: AuthStack, me: Me, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.AD)

    with pytest.raises(InvalidStateError) as caught:
        await _change(auth, me)

    assert str(caught.value) == LOCAL_MODE_ONLY
    assert await session_is_active(uow_factory, me.other_a.token)


@pytest.mark.parametrize("login_id", ["dev-admin", "dev-sales", "dev-user"])
async def test_change_my_password_dev_user_is_invalid_state(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, login_id: str
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    dev = await seed_local_user(uow_factory, login_id, OLD, Role.ADMIN)
    issued = await auth.issue.execute(dev.to_principal())

    with pytest.raises(InvalidStateError):
        await auth.change_my_password.execute(
            actor=dev.to_principal(),
            current=Password(OLD),
            new=Password(NEW),
            session_token=issued.token,
            client_ip=IP,
        )


async def test_change_my_password_for_a_user_without_a_hash_is_wrong_current(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await seed_local_user(uow_factory, "kim", OLD, with_hash=False)
    issued = await auth.issue.execute(kim.to_principal())

    with pytest.raises(WrongCurrentPasswordError):
        await auth.change_my_password.execute(
            actor=kim.to_principal(),
            current=Password(OLD),
            new=Password(NEW),
            session_token=issued.token,
            client_ip=IP,
        )


async def test_change_my_password_verifies_and_hashes_outside_any_transaction(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork
) -> None:
    auth.hasher.open_units_probe = lambda: uow.open_units
    seen: list[int] = []
    original = auth.hasher.hash

    async def spy(password: Password):  # type: ignore[no-untyped-def]  # noqa: ANN202
        seen.append(uow.open_units)
        return await original(password)

    auth.hasher.hash = spy  # type: ignore[method-assign]

    await _change(auth, me)

    assert auth.hasher.open_units_at_verify == [0]
    assert seen == [0]


async def test_the_session_to_keep_is_the_one_whose_token_was_given(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork
) -> None:
    await _change(auth, me, token=me.other_a.token)

    assert hash_token(me.other_a.token) in uow.sessions._items
    assert hash_token(me.current.token) not in uow.sessions._items
