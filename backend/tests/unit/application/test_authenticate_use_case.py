"""세션 인증(Authenticate)·IssueSession·Logout (AUTH-10~12, AC4, T14·T27)."""

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from app.application.auth.authenticate import Authenticate
from app.application.auth.tokens import hash_token
from app.domain.auth.credentials import LoginId
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from tests.factories import NOW
from tests.factories_auth import make_principal
from tests.fakes.auth_stack import SESSION_TTL
from tests.support.auth_seed import seed_user

if TYPE_CHECKING:
    from app.application.auth.issue_session import IssuedSession
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


async def _issue_for(auth: AuthStack, uow_factory: UnitOfWorkFactory) -> IssuedSession:
    user = await seed_user(uow_factory, "kim", Role.SALES)
    return await auth.issue.execute(user.to_principal())


async def test_token_authenticates_the_registered_user_until_it_expires(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """발급한 세션은 만료 전까지 인증되고 만료 시각부터 401이다.

    테스트 코드: AU-053
    """
    # given: 등록된 kim에게 세션을 발급했다
    user = await seed_user(uow_factory, "kim", Role.SALES)
    issued = await auth.issue.execute(user.to_principal())

    # when: 만료 전에 인증하고 TTL이 지난 뒤 다시 인증한다
    principal = await auth.authenticate.execute(issued.token)
    clock.advance(int(SESSION_TTL.total_seconds()))

    # then: 만료 전에는 인증되고 만료 시각부터는 인증 실패다
    assert principal.subject == "kim"
    assert principal.user_id == user.id
    assert issued.expires_at == NOW + SESSION_TTL
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


async def test_role_is_read_from_the_users_table_on_every_request(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """역할은 요청마다 users 행에서 읽는다.

    테스트 코드: AU-056
    """
    # given: 세션 주체의 역할은 admin이지만 users 행은 sales이고 나중에 user로 바뀐다
    user = await seed_user(uow_factory, "kim", Role.SALES)
    forged = replace(user.to_principal(), role=Role.ADMIN)  # 세션에 적힌 역할은 무시된다
    issued = await auth.issue.execute(forged)

    # when: 발급한 세션으로 인증한다
    authenticated = await auth.authenticate.execute(issued.token)

    # then: 세션에 적힌 역할이 아닌 users 행의 역할(sales)이다. 행이 바뀌면 다음 요청에 반영된다
    assert authenticated.role is Role.SALES
    async with uow_factory() as uow:
        stored = await uow.users.get_active_by_login_id(LoginId("kim"))
        assert stored is not None
        stored.role = Role.USER
        await uow.users.update(stored)
        await uow.commit()

    assert (await auth.authenticate.execute(issued.token)).role is Role.USER


async def test_profile_comes_from_the_users_table(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """이름·이메일은 요청마다 users 행에서 읽는다.

    테스트 코드: AU-056
    """
    # given: 이름·이메일이 저장된 kim의 세션
    user = await seed_user(uow_factory, "kim", Role.SALES)
    async with uow_factory() as uow:
        user.record_login(NOW, display_name="김영업", email="kim@corp.test")
        await uow.users.update(user)
        await uow.commit()
    issued = await auth.issue.execute(user.to_principal())

    # when: 인증한다
    principal = await auth.authenticate.execute(issued.token)

    # then: users 행의 이름·이메일이다
    assert (principal.name, principal.email) == ("김영업", "kim@corp.test")


async def test_physically_deleted_users_session_is_rejected_from_the_next_request(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """삭제된 사용자의 세션은 다음 요청부터 401이다.

    테스트 코드: AU-057
    """
    # given: kim의 세션이 인증되던 중 kim이 삭제된다
    user = await seed_user(uow_factory, "kim", Role.SALES)
    issued = await auth.issue.execute(user.to_principal())
    assert (await auth.authenticate.execute(issued.token)).subject == "kim"
    async with uow_factory() as uow:
        await uow.users.delete(user.id)
        await uow.commit()

    # when·then: 같은 세션으로 요청한다 → 인증 실패다
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


async def test_resigned_users_token_is_rejected_even_if_the_session_row_survives(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """퇴사한 사용자의 세션은 세션 행이 남아 있어도 401이다.

    테스트 코드: AU-057
    """
    # given: kim의 세션이 있고 kim이 퇴사 처리된다
    user = await seed_user(uow_factory, "kim", Role.SALES)
    issued = await auth.issue.execute(user.to_principal())
    async with uow_factory() as uow:
        stored = await uow.users.get(user.id)
        stored.resign(NOW)
        await uow.users.update(stored)
        await uow.commit()

    # when: 같은 세션으로 요청한다
    with pytest.raises(AuthenticationError) as caught:
        await auth.authenticate.execute(issued.token)

    # then: 인증 실패다
    assert type(caught.value) is AuthenticationError


async def test_a_new_active_row_with_the_same_login_id_does_not_revive_the_old_token(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """같은 아이디로 다시 등록해도 이전 세션은 살아나지 않는다.

    테스트 코드: AU-058
    """
    # given: 퇴사한 kim의 세션과 같은 아이디의 새 재직 행
    old = await seed_user(uow_factory, "kim", Role.SALES, resigned=True)
    await seed_user(uow_factory, "kim", Role.SALES)
    issued = await auth.issue.execute(old.to_principal())

    # when·then: 예전 세션으로 요청한다 → 인증 실패다
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


async def test_session_of_an_unregistered_user_is_rejected(auth: AuthStack) -> None:
    """users에 없는 사용자의 세션은 인증되지 않는다."""
    # given: users에 없는 주체의 세션
    issued = await auth.issue.execute(make_principal("ghost"))

    # when·then: 인증한다 → 인증 실패다
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


async def test_session_with_a_subject_that_is_not_a_login_id_is_unauthenticated(
    auth: AuthStack,
) -> None:
    """아이디 형식이 아닌 주체의 세션은 인증되지 않는다."""
    # given: 아이디 형식이 아닌 주체의 세션
    issued = await auth.issue.execute(make_principal("Not A Login!"))

    # when: 인증한다
    with pytest.raises(AuthenticationError) as caught:
        await auth.authenticate.execute(issued.token)

    # then: 공통 인증 실패다
    assert type(caught.value) is AuthenticationError


async def test_only_the_hash_of_the_token_is_stored(
    auth: AuthStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """저장소에는 토큰 해시만 있고 토큰 원문은 없다.

    테스트 코드: AU-054
    """
    # given: kim에게 세션을 발급했다
    issued = await _issue_for(auth, uow_factory)

    # when: 토큰 원문과 토큰 해시로 저장소를 조회한다
    assert await uow.sessions.get_by_token_hash(issued.token) is None
    # then: 해시로만 세션이 찾아진다
    assert await uow.sessions.get_by_token_hash(hash_token(issued.token)) is not None


@pytest.mark.parametrize("token", [None, "", "unknown-token"])
async def test_missing_or_unknown_token_is_unauthenticated(
    auth: AuthStack, token: str | None
) -> None:
    """쿠키가 없거나 발급한 적 없는 토큰이면 인증 실패다.

    테스트 코드: AU-055
    """
    # when·then: 토큰 없음·빈 값·모르는 토큰으로 인증한다 → 인증 실패다
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(token)


async def test_tokens_are_unique(auth: AuthStack, uow_factory: UnitOfWorkFactory) -> None:
    """발급할 때마다 토큰이 다르다.

    테스트 코드: AU-054
    """
    # given: kim에게 세션을 발급했다
    first = await _issue_for(auth, uow_factory)
    # when: 같은 주체로 다시 발급한다
    second = await auth.issue.execute(first.principal)

    # then: 두 토큰이 다르다
    assert first.token != second.token


async def test_logout_revokes_the_session(auth: AuthStack, uow_factory: UnitOfWorkFactory) -> None:
    """로그아웃하면 세션이 폐기되어 이후 요청은 401이다.

    테스트 코드: AU-060
    """
    # given: kim의 세션
    issued = await _issue_for(auth, uow_factory)

    # when: 로그아웃한다
    await auth.logout.execute(issued.token)

    # then: 같은 토큰으로 인증하면 실패한다
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


@pytest.mark.parametrize("token", [None, "unknown"])
async def test_logout_is_idempotent_for_missing_sessions(
    auth: AuthStack, token: str | None
) -> None:
    """토큰이 없거나 모르는 토큰으로 로그아웃해도 무해하다.

    테스트 코드: AU-061
    """
    # when·then: 세션이 없는 토큰으로 로그아웃한다 → 예외 없이 끝난다
    await auth.logout.execute(token)


async def test_revoking_twice_is_harmless(auth: AuthStack, uow_factory: UnitOfWorkFactory) -> None:
    """이미 폐기된 세션을 다시 로그아웃해도 무해하다.

    테스트 코드: AU-061
    """
    # given: kim의 세션
    issued = await _issue_for(auth, uow_factory)

    await auth.logout.execute(issued.token)
    # when: 두 번째로 로그아웃한다
    await auth.logout.execute(issued.token)

    # then: 예외 없이 끝나고 토큰은 계속 인증 실패다
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


def test_authenticate_has_no_switch_to_allow_dev_users(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """인증 유스케이스에는 개발용 사용자 허용 스위치가 없다."""
    # when·then: 허용 스위치를 주고 만들면 → TypeError다
    with pytest.raises(TypeError):
        Authenticate(uow_factory, clock, allow_dev_users=True)  # type: ignore[call-arg]
