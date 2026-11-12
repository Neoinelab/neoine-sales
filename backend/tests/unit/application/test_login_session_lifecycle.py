"""로그인과 사용자 상태 변화(AU): 삭제·재등록·AD 복구 뒤의 세션과 해시."""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from tests.support.auth_seed import seed_directory, seed_password_hash, seed_user

if TYPE_CHECKING:
    from app.application.auth.directory_login import LoginOutcome
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

IP = "10.0.0.1"


async def _login(auth: AuthStack) -> LoginOutcome:
    return await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)


async def test_deleted_user_cannot_log_in_again_and_the_old_session_is_dead(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """삭제된 사용자는 AD 계정이 남아 있어도 다시 로그인할 수 없고 이전 세션도 401이다.

    테스트 코드: AU-057
    """
    # given: AD 계정이 있는 kim이 로그인해 세션을 받았고, 그 뒤 kim이 삭제되었다
    await seed_directory(uow_factory)
    user = await seed_user(uow_factory, "kim", Role.SALES)
    issued = (
        await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)
    ).session
    async with uow_factory() as uow:
        await uow.users.delete(user.id)
        await uow.commit()

    # when: 같은 AD 비밀번호로 다시 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    # then: 공통 실패이고 이전 세션 토큰도 인증되지 않는다
    assert type(caught.value) is AuthenticationError
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(issued.token)


async def test_reregistered_login_id_logs_in_as_the_new_row_while_the_old_session_stays_dead(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """같은 아이디로 다시 등록해도 이전 세션은 401이고 새 사용자는 새로 로그인한다.

    테스트 코드: AU-058
    """
    # given: kim이 로그인해 세션을 받았고, 퇴사 처리된 뒤 같은 아이디로 새 행이 등록되었다
    await seed_directory(uow_factory)
    old = await seed_user(uow_factory, "kim", Role.USER)
    old_session = (
        await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)
    ).session
    async with uow_factory() as uow:
        stored = await uow.users.get(old.id)
        stored.resign(old_session.expires_at)
        await uow.users.update(stored)
        await uow.commit()
    new = await seed_user(uow_factory, "kim", Role.SALES)

    # when: kim이 다시 로그인한다
    fresh = (
        await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)
    ).session

    # then: 새 행(sales)의 세션이고 예전 토큰은 계속 인증되지 않는다
    assert fresh.principal.user_id == new.id
    assert fresh.principal.user_id != old.id
    assert fresh.principal.role is Role.SALES
    assert (await auth.authenticate.execute(fresh.token)).user_id == new.id
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(old_session.token)


async def test_login_after_the_directory_recovers_goes_through_it_and_refreshes_the_hash(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    """AD가 돌아오면 다음 로그인은 AD를 거치고 해시가 새로 저장된다.

    테스트 코드: AU-027
    """
    # given: 해시가 있는 kim이 AD 연결 불가 중 대체 로그인했고, 그 뒤 AD가 복구되었다
    await seed_directory(uow_factory)
    kim = await seed_user(uow_factory, "kim", Role.SALES)
    await seed_password_hash(uow_factory, kim, "pw-kim")
    auth.directory.authenticate_fails_with = DirectoryUnavailableError(
        stage=VerificationStage.CONNECT
    )
    await _login(auth)
    during_outage = await uow.password_hashes.get(kim.id)
    auth.directory.authenticate_fails_with = None
    auth.directory.authenticate_calls.clear()
    clock.advance(3600)

    # when: kim이 다시 로그인한다
    outcome = await _login(auth)

    # then: AD를 한 번 거쳤고 경고가 없으며 해시가 새 값으로 바뀌었다
    assert len(auth.directory.authenticate_calls) == 1
    assert outcome.directory_warning is None
    refreshed = await uow.password_hashes.get(kim.id)
    assert refreshed is not None
    assert refreshed != during_outage
    assert await auth.hasher.verify(Password("pw-kim"), refreshed)
    stored = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert stored is not None
    assert stored.last_login_at == clock.now()
