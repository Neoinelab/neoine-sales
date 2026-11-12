"""ResetUserPassword: local 모드 admin이 다른 사용자의 비밀번호를 재설정한다.

대상의 모든 세션을 끝낸다(요청한 admin 자신의 세션은 그대로). ad 모드·자기 자신·퇴사자·dev 사용자는
InvalidStateError, 정책 위반은 InvalidValueError.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import LOCAL_MODE_ONLY
from app.domain.auth.credentials import Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.user.errors import UserNotFoundError
from tests.fakes.password_hasher import fake_hash_of
from tests.support.admin_seed import session_is_active
from tests.support.auth_seed import seed_auth_mode, seed_local_user
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

OLD = "old-password-1"  # 가짜 값
NEW = "New-passw0rd"  # 가짜 값


@pytest.fixture
async def boss(uow_factory: UnitOfWorkFactory) -> Principal:
    """local 모드의 admin 요청자(users 행이 있다)."""
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    user = await seed_local_user(uow_factory, "boss", "boss-password-1", Role.ADMIN)
    return user.to_principal()


async def test_reset_password_saves_hash_and_ends_target_sessions(
    admin: AdminStack,
    auth: AuthStack,
    boss: Principal,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
) -> None:
    """비밀번호를 재설정하면 새 해시가 저장되고 대상의 세션이 모두 끝난다

    테스트 코드: US-049
    """
    # given: kim의 세션 둘과 요청 admin의 세션
    kim = await seed_local_user(uow_factory, "kim", OLD)
    first = await auth.issue.execute(kim.to_principal())
    second = await auth.issue.execute(kim.to_principal())
    boss_session = await auth.issue.execute(boss)

    # when: kim의 비밀번호를 재설정한다
    await admin.reset_password.execute(user_id=kim.id, password=Password(NEW), actor=boss)

    # then: 새 비밀번호의 해시만 맞고 kim의 세션은 끝나며 admin의 세션은 유지된다
    saved = await uow.password_hashes.get(kim.id)
    assert saved is not None
    assert await auth.hasher.verify(Password(NEW), saved) is True
    assert await auth.hasher.verify(Password(OLD), saved) is False
    assert not await session_is_active(uow_factory, first.token)
    assert not await session_is_active(uow_factory, second.token)
    assert await session_is_active(uow_factory, boss_session.token)


async def test_reset_password_leaves_other_users_sessions_and_hashes(
    admin: AdminStack, auth: AuthStack, boss: Principal, uow_factory: UnitOfWorkFactory
) -> None:
    """재설정해도 다른 사용자의 세션·해시는 그대로다

    테스트 코드: US-050
    """
    # given: kim과 lee, lee의 세션
    kim = await seed_local_user(uow_factory, "kim", OLD)
    lee = await seed_local_user(uow_factory, "lee", "lee-password-1")
    lee_session = await auth.issue.execute(lee.to_principal())

    # when: kim의 비밀번호를 재설정한다
    await admin.reset_password.execute(user_id=kim.id, password=Password(NEW), actor=boss)

    # then: lee의 세션과 해시가 그대로다
    assert await session_is_active(uow_factory, lee_session.token)
    async with uow_factory() as uow:
        assert await uow.password_hashes.get(lee.id) == fake_hash_of("lee-password-1")


async def test_reset_password_then_the_target_signs_in_with_the_new_password_only(
    admin: AdminStack, auth: AuthStack, boss: Principal, uow_factory: UnitOfWorkFactory
) -> None:
    """재설정 뒤 대상은 새 비밀번호로만 로그인된다

    테스트 코드: US-049
    """
    # given: kim
    kim = await seed_local_user(uow_factory, "kim", OLD)

    # when: 비밀번호를 재설정한다
    await admin.reset_password.execute(user_id=kim.id, password=Password(NEW), actor=boss)

    # then: 새 비밀번호로는 로그인되고 옛 비밀번호로는 인증 오류다
    outcome = await auth.password_login.execute(
        login_id="kim", password=Password(NEW), client_ip="10.0.0.1"
    )
    assert outcome.session.principal.subject == "kim"
    with pytest.raises(AuthenticationError):
        await auth.password_login.execute(
            login_id="kim", password=Password(OLD), client_ip="10.0.0.1"
        )


async def test_reset_password_creates_a_hash_for_a_user_without_one(
    admin: AdminStack, boss: Principal, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """해시가 없던 사용자도 재설정하면 해시가 생긴다

    테스트 코드: US-051
    """
    # given: 해시가 없는 kim
    kim = await seed_local_user(uow_factory, "kim", OLD, with_hash=False)

    # when: 비밀번호를 재설정한다
    await admin.reset_password.execute(user_id=kim.id, password=Password(NEW), actor=boss)

    # then: kim의 해시가 저장된다
    assert await uow.password_hashes.get(kim.id) is not None


async def test_reset_password_in_ad_mode_is_invalid_state(
    admin: AdminStack, boss: Principal, uow_factory: UnitOfWorkFactory
) -> None:
    """AD 모드에서는 재설정이 상태 오류이고 해시는 그대로다

    테스트 코드: US-052
    """
    # given: AD 모드, 해시가 있는 kim
    kim = await seed_local_user(uow_factory, "kim", OLD)
    await seed_auth_mode(uow_factory, AuthMode.AD)

    # when: 재설정한다
    with pytest.raises(InvalidStateError) as caught:
        await admin.reset_password.execute(user_id=kim.id, password=Password(NEW), actor=boss)

    # then: local 전용 문구의 상태 오류이고 해시가 그대로다
    assert str(caught.value) == LOCAL_MODE_ONLY
    async with uow_factory() as uow:
        assert await uow.password_hashes.get(kim.id) == fake_hash_of(OLD)


async def test_reset_password_without_a_mode_row_in_a_legacy_system_is_invalid_state(
    admin: AdminStack, boss: Principal, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """모드 행이 없는 기존 시스템도 AD로 보아 재설정을 거절한다

    테스트 코드: US-052
    """
    # given: 모드 행이 없는 시스템
    kim = await seed_local_user(uow_factory, "kim", OLD)
    uow.auth_settings._items.clear()  # admin이 있고 방식 행이 없다 = 기존 AD 시스템

    # when: 재설정한다
    with pytest.raises(InvalidStateError):
        await admin.reset_password.execute(user_id=kim.id, password=Password(NEW), actor=boss)
    # then: 상태 오류다


async def test_reset_password_of_self_is_invalid_state(
    admin: AdminStack,
    auth: AuthStack,
    boss: Principal,
    uow: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
) -> None:
    """자기 자신의 비밀번호는 재설정할 수 없다

    테스트 코드: US-053
    """
    # given: 요청 admin의 세션
    session = await auth.issue.execute(boss)

    # when: 자기 비밀번호를 재설정한다
    with pytest.raises(InvalidStateError):
        await admin.reset_password.execute(user_id=boss.user_id, password=Password(NEW), actor=boss)

    # then: 상태 오류이고 해시·세션이 그대로다
    assert await uow.password_hashes.get(boss.user_id) == fake_hash_of("boss-password-1")
    assert await session_is_active(uow_factory, session.token)  # 세션도 그대로


async def test_reset_password_of_resigned_user_is_invalid_state(
    admin: AdminStack, boss: Principal, uow_factory: UnitOfWorkFactory
) -> None:
    """퇴사자의 비밀번호는 재설정할 수 없다

    테스트 코드: US-054
    """
    # given: 퇴사한 사용자
    gone = await seed_local_user(uow_factory, "gone", OLD, resigned=True)

    # when: 재설정한다
    with pytest.raises(InvalidStateError):
        await admin.reset_password.execute(user_id=gone.id, password=Password(NEW), actor=boss)
    # then: 상태 오류다


@pytest.mark.parametrize("password", ["short7!", "kim", "1234567"])
async def test_reset_password_weak_password_is_invalid_value_and_changes_nothing(
    admin: AdminStack,
    auth: AuthStack,
    boss: Principal,
    uow_factory: UnitOfWorkFactory,
    password: str,
) -> None:
    """약한 비밀번호로 재설정하면 입력 오류이고 기존 해시·세션이 그대로다

    테스트 코드: US-055
    """
    # given: kim과 그의 세션
    kim = await seed_local_user(uow_factory, "kim", OLD)
    session = await auth.issue.execute(kim.to_principal())

    # when: 약한 비밀번호로 재설정한다
    with pytest.raises(InvalidValueError):
        await admin.reset_password.execute(user_id=kim.id, password=Password(password), actor=boss)

    # then: 입력 오류이고 해시·세션이 그대로다
    async with uow_factory() as uow:
        assert await uow.password_hashes.get(kim.id) == fake_hash_of(OLD)
    assert await session_is_active(uow_factory, session.token)


async def test_reset_password_unknown_user_is_not_found(admin: AdminStack, boss: Principal) -> None:
    """없는 사용자의 재설정은 없음 오류다

    테스트 코드: US-056
    """
    # when: 없는 id를 재설정한다
    with pytest.raises(UserNotFoundError):
        await admin.reset_password.execute(user_id=uid("ghost"), password=Password(NEW), actor=boss)
    # then: 사용자 없음 오류다
