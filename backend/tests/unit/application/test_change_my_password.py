"""ChangeMyPassword: local 사용자가 현재 비밀번호를 확인하고 자기 비밀번호를 바꾼다 (ME-R9~R13).

현재 비밀번호 확인은 로그인과 같은 시도 제한을 공유한다.
틀리면 실패 1회, 잠기면 TooManyAttemptsError다.
성공하면 지금 세션은 두고 그 사용자의 다른 세션만 끝낸다. ad 모드는 InvalidStateError.
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
    """비밀번호를 바꾸면 현재 세션은 남고 같은 사용자의 다른 세션만 끝난다.

    테스트 코드: ME-018
    """
    # when: 현재 세션으로 비밀번호를 바꾼다
    #   (전제: local 모드이고 kim의 세션 셋(현재·다른 둘)이 있다)
    await _change(auth, me)

    # then: 현재 세션은 살아 있고 다른 둘은 끝났다
    assert await session_is_active(uow_factory, me.current.token)
    assert not await session_is_active(uow_factory, me.other_a.token)
    assert not await session_is_active(uow_factory, me.other_b.token)
    assert (await auth.authenticate.execute(me.current.token)).subject == "kim"


async def test_change_my_password_does_not_touch_other_users_sessions(
    auth: AuthStack, me: Me, uow_factory: UnitOfWorkFactory
) -> None:
    """다른 사용자의 세션은 그대로 살아 있다.

    테스트 코드: ME-018
    """
    # given: kim의 세션들과 lee의 세션 하나가 있다
    lee = await seed_local_user(uow_factory, "lee", "lee-password-1")
    lee_session = await auth.issue.execute(lee.to_principal())

    # when: kim이 비밀번호를 바꾼다
    await _change(auth, me)

    # then: lee의 세션은 살아 있다
    assert await session_is_active(uow_factory, lee_session.token)


async def test_change_my_password_new_password_signs_in_and_old_does_not(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork
) -> None:
    """비밀번호를 바꾸면 새 비밀번호로만 확인된다.

    테스트 코드: ME-017
    """
    # when: 새 비밀번호로 바꾼다 (전제: local 모드이고 kim(현재 비밀번호 OLD)이 있다)
    await _change(auth, me)

    # then: 저장된 해시는 새 비밀번호만 통과시킨다
    stored = await uow.password_hashes.get(me.actor.user_id)
    assert stored is not None
    assert await auth.hasher.verify(Password(NEW), stored) is True
    assert await auth.hasher.verify(Password(OLD), stored) is False


async def test_change_my_password_success_clears_the_account_counter(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork
) -> None:
    """비밀번호 변경에 성공하면 계정 실패 카운터가 지워진다.

    테스트 코드: ME-023
    """
    # given: kim이 현재 비밀번호를 한 번 틀려 계정 실패 수가 1이다
    with pytest.raises(WrongCurrentPasswordError):
        await _change(auth, me, current="wrong-password")
    assert uow.login_failures._items[account_key("kim")].failures == 1

    # when: 맞는 현재 비밀번호로 바꾼다
    await _change(auth, me)

    # then: kim 계정 실패 카운터가 없다
    assert account_key("kim") not in uow.login_failures._items


async def test_change_my_password_wrong_current_is_invalid_value_and_counted(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """현재 비밀번호가 틀리면 InvalidValueError이고 실패 1회로 세며 세션은 그대로다.

    테스트 코드: ME-020
    """
    # when: 틀린 현재 비밀번호로 바꾸려 한다 (전제: local 모드이고 kim의 세션들이 있다)
    with pytest.raises(WrongCurrentPasswordError) as caught:
        await _change(auth, me, current="wrong-password")

    # then: 고정 문구, 계정 실패 수 1, 해시는 이전 그대로, 다른 세션도 살아 있다
    assert isinstance(caught.value, InvalidValueError)
    assert str(caught.value) == "현재 비밀번호가 올바르지 않습니다."
    assert uow.login_failures._items[account_key("kim")].failures == 1
    assert await uow.password_hashes.get(me.actor.user_id) == fake_hash_of(OLD)
    assert await session_is_active(uow_factory, me.other_a.token)  # 실패하면 세션은 그대로


async def test_change_my_password_locked_is_too_many_attempts_without_verifying(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork
) -> None:
    """실패 한도를 넘으면 맞는 현재 비밀번호여도 확인 없이 TooManyAttemptsError다.

    테스트 코드: ME-021
    """
    # given: kim이 현재 비밀번호를 계정 한도만큼 틀렸다
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(WrongCurrentPasswordError):
            await _change(auth, me, current="wrong-password")
    verified = len(auth.hasher.verify_calls)

    # when: 맞는 현재 비밀번호로 다시 요청한다
    with pytest.raises(TooManyAttemptsError):
        await _change(auth, me)  # 올바른 현재 비밀번호여도 잠겨 있다

    # then: 비밀번호 확인 계산은 더 일어나지 않았고 해시는 이전 그대로다
    assert len(auth.hasher.verify_calls) == verified
    assert await uow.password_hashes.get(me.actor.user_id) == fake_hash_of(OLD)


async def test_change_my_password_failures_are_shared_with_login(auth: AuthStack, me: Me) -> None:
    """현재 비밀번호 실패는 로그인과 같은 카운터를 쓴다.

    테스트 코드: ME-022
    """
    # given: kim이 비밀번호 변경에서 현재 비밀번호를 계정 한도만큼 틀렸다
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(WrongCurrentPasswordError):
            await _change(auth, me, current="wrong-password")

    # when·then: kim이 맞는 비밀번호로 로그인한다 → 로그인은 TooManyAttemptsError다
    with pytest.raises(TooManyAttemptsError):
        await auth.password_login.execute(login_id="kim", password=Password(OLD), client_ip=IP)


@pytest.mark.parametrize("new", ["short7!", "1234567", "kim"])
async def test_change_my_password_weak_new_password_is_invalid_value_and_not_counted(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork, new: str
) -> None:
    """8자 미만 새 비밀번호는 WeakPasswordError이고 실패로 세지 않는다.

    테스트 코드: ME-024
    """
    # when: 맞는 현재 비밀번호와 8자 미만 새 비밀번호로 바꾸려 한다
    #   (전제: local 모드이고 kim(현재 비밀번호 OLD)이 있다)
    with pytest.raises(WeakPasswordError) as caught:
        await _change(auth, me, new=new)

    # then: 현재 비밀번호 오류가 아니고 실패 카운터가 없으며 해시는 그대로다
    assert not isinstance(caught.value, WrongCurrentPasswordError)
    assert uow.login_failures._items == {}
    assert await uow.password_hashes.get(me.actor.user_id) == fake_hash_of(OLD)


@pytest.mark.parametrize("new", ["Kim.Lee1", " kim.lee1 ", "KIM.LEE1"])
async def test_change_my_password_new_equal_to_login_id_is_invalid_value(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, new: str
) -> None:
    """아이디와 같은 새 비밀번호는 대소문자·앞뒤 공백을 무시하고 거절한다.

    테스트 코드: ME-025
    """
    # given: local 모드이고 아이디 kim.lee1 사용자가 세션을 가졌다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await seed_local_user(uow_factory, "kim.lee1", OLD)
    issued = await auth.issue.execute(kim.to_principal())

    # when: 아이디와 같은(대소문자·공백만 다른) 새 비밀번호로 바꾸려 한다
    with pytest.raises(WeakPasswordError) as caught:
        await auth.change_my_password.execute(
            actor=kim.to_principal(),
            current=Password(OLD),
            new=Password(new),
            session_token=issued.token,
            client_ip=IP,
        )

    # then: 아이디와 같을 수 없다는 문구다
    assert "아이디와 같을 수 없습니다" in str(caught.value)


@pytest.mark.parametrize("new", ["abcd1234", "x" * 256])
async def test_change_my_password_accepts_exactly_the_minimum_and_maximum_length(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork, new: str
) -> None:
    """정확히 8자·256자 새 비밀번호는 받아들인다.

    테스트 코드: ME-026
    """
    # when: 경계 길이의 새 비밀번호로 바꾼다 (전제: local 모드이고 kim(현재 비밀번호 OLD)이 있다)
    await _change(auth, me, new=new)

    # then: 저장된 해시가 그 새 비밀번호를 통과시킨다
    stored = await uow.password_hashes.get(me.actor.user_id)
    assert stored is not None
    assert await auth.hasher.verify(Password(new), stored) is True


async def test_change_my_password_in_ad_mode_is_invalid_state(
    auth: AuthStack, me: Me, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """AD 모드에서 비밀번호를 바꾸려 하면 InvalidStateError이고 세션·카운터는 그대로다.

    테스트 코드: ME-027
    """
    # given: AD 모드이고 kim의 세션들이 있다
    await seed_auth_mode(uow_factory, AuthMode.AD)

    # when: 비밀번호 변경을 요청한다
    with pytest.raises(InvalidStateError) as caught:
        await _change(auth, me)

    # then: local 전용 문구이고 다른 세션은 살아 있으며 실패 카운터가 없다
    assert str(caught.value) == LOCAL_MODE_ONLY
    assert await session_is_active(uow_factory, me.other_a.token)
    assert uow.login_failures._items == {}


async def test_change_my_password_for_a_user_without_a_hash_is_wrong_current(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """저장된 해시가 없는 사용자는 현재 비밀번호 틀림과 같다.

    테스트 코드: ME-028
    """
    # given: local 모드이고 비밀번호 해시가 없는 kim이 세션을 가졌다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await seed_local_user(uow_factory, "kim", OLD, with_hash=False)
    issued = await auth.issue.execute(kim.to_principal())

    # when·then: 아무 현재 비밀번호로 변경을 요청한다 → WrongCurrentPasswordError다
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
    """비밀번호 확인과 해시 계산은 DB 트랜잭션 밖에서 한다.

    BDD 케이스 밖 단위 테스트(ME-R13).
    """
    # given: 확인·해시가 불린 시점의 열린 UoW 수를 재는 Fake
    auth.hasher.open_units_probe = lambda: uow.open_units
    seen: list[int] = []
    original = auth.hasher.hash

    async def spy(password: Password):  # type: ignore[no-untyped-def]  # noqa: ANN202
        seen.append(uow.open_units)
        return await original(password)

    auth.hasher.hash = spy  # type: ignore[method-assign]

    # when: 비밀번호를 바꾼다
    await _change(auth, me)

    # then: 확인과 해시 계산 때 열린 UoW가 없었다
    assert auth.hasher.open_units_at_verify == [0]
    assert seen == [0]


async def test_the_session_to_keep_is_the_one_whose_token_was_given(
    auth: AuthStack, me: Me, uow: FakeUnitOfWork
) -> None:
    """유지하는 세션은 요청 쿠키의 세션(넘겨 준 토큰)이다.

    테스트 코드: ME-019
    """
    # when: 세션 A의 토큰으로 비밀번호를 바꾼다 (전제: kim의 세션 A(other_a)·B가 있다)
    await _change(auth, me, token=me.other_a.token)

    # then: 세션 저장소에 A는 남고 현재 세션이던 것은 지워진다
    assert hash_token(me.other_a.token) in uow.sessions._items
    assert hash_token(me.current.token) not in uow.sessions._items
