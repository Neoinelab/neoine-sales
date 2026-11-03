"""ResetUserPassword: local 모드 admin이 다른 사용자의 비밀번호를 재설정한다 (AC-7).

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
    kim = await seed_local_user(uow_factory, "kim", OLD)
    first = await auth.issue.execute(kim.to_principal())
    second = await auth.issue.execute(kim.to_principal())
    boss_session = await auth.issue.execute(boss)

    await admin.reset_password.execute(user_id=kim.id, password=Password(NEW), actor=boss)

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
    kim = await seed_local_user(uow_factory, "kim", OLD)
    lee = await seed_local_user(uow_factory, "lee", "lee-password-1")
    lee_session = await auth.issue.execute(lee.to_principal())

    await admin.reset_password.execute(user_id=kim.id, password=Password(NEW), actor=boss)

    assert await session_is_active(uow_factory, lee_session.token)
    async with uow_factory() as uow:
        assert await uow.password_hashes.get(lee.id) == fake_hash_of("lee-password-1")


async def test_reset_password_then_the_target_signs_in_with_the_new_password_only(
    admin: AdminStack, auth: AuthStack, boss: Principal, uow_factory: UnitOfWorkFactory
) -> None:
    kim = await seed_local_user(uow_factory, "kim", OLD)

    await admin.reset_password.execute(user_id=kim.id, password=Password(NEW), actor=boss)

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
    kim = await seed_local_user(uow_factory, "kim", OLD, with_hash=False)

    await admin.reset_password.execute(user_id=kim.id, password=Password(NEW), actor=boss)

    assert await uow.password_hashes.get(kim.id) is not None


async def test_reset_password_in_ad_mode_is_invalid_state(
    admin: AdminStack, boss: Principal, uow_factory: UnitOfWorkFactory
) -> None:
    kim = await seed_local_user(uow_factory, "kim", OLD)
    await seed_auth_mode(uow_factory, AuthMode.AD)

    with pytest.raises(InvalidStateError) as caught:
        await admin.reset_password.execute(user_id=kim.id, password=Password(NEW), actor=boss)

    assert str(caught.value) == LOCAL_MODE_ONLY
    async with uow_factory() as uow:
        assert await uow.password_hashes.get(kim.id) == fake_hash_of(OLD)


async def test_reset_password_without_a_mode_row_in_a_legacy_system_is_invalid_state(
    admin: AdminStack, boss: Principal, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    kim = await seed_local_user(uow_factory, "kim", OLD)
    uow.auth_settings._items.clear()  # admin이 있고 방식 행이 없다 = 기존 AD 시스템

    with pytest.raises(InvalidStateError):
        await admin.reset_password.execute(user_id=kim.id, password=Password(NEW), actor=boss)


async def test_reset_password_of_self_is_invalid_state(
    admin: AdminStack,
    auth: AuthStack,
    boss: Principal,
    uow: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
) -> None:
    session = await auth.issue.execute(boss)

    with pytest.raises(InvalidStateError):
        await admin.reset_password.execute(user_id=boss.user_id, password=Password(NEW), actor=boss)

    assert await uow.password_hashes.get(boss.user_id) == fake_hash_of("boss-password-1")
    assert await session_is_active(uow_factory, session.token)  # 세션도 그대로


async def test_reset_password_of_resigned_user_is_invalid_state(
    admin: AdminStack, boss: Principal, uow_factory: UnitOfWorkFactory
) -> None:
    gone = await seed_local_user(uow_factory, "gone", OLD, resigned=True)

    with pytest.raises(InvalidStateError):
        await admin.reset_password.execute(user_id=gone.id, password=Password(NEW), actor=boss)


@pytest.mark.parametrize("password", ["short7!", "kim", "1234567"])
async def test_reset_password_weak_password_is_invalid_value_and_changes_nothing(
    admin: AdminStack,
    auth: AuthStack,
    boss: Principal,
    uow_factory: UnitOfWorkFactory,
    password: str,
) -> None:
    kim = await seed_local_user(uow_factory, "kim", OLD)
    session = await auth.issue.execute(kim.to_principal())

    with pytest.raises(InvalidValueError):
        await admin.reset_password.execute(user_id=kim.id, password=Password(password), actor=boss)

    async with uow_factory() as uow:
        assert await uow.password_hashes.get(kim.id) == fake_hash_of(OLD)
    assert await session_is_active(uow_factory, session.token)


async def test_reset_password_unknown_user_is_not_found(admin: AdminStack, boss: Principal) -> None:
    with pytest.raises(UserNotFoundError):
        await admin.reset_password.execute(user_id=uid("ghost"), password=Password(NEW), actor=boss)
