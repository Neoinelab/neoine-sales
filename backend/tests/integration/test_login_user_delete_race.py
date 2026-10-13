"""로그인의 last-login 갱신과 사용자 삭제가 겹쳐도 로그인은 LOGIN_FAILED로 끝난다(Minor 3).

삭제 트랜잭션이 DELETE를 flush했지만 아직 커밋하지 않은 동안 로그인의 UPDATE가 행 잠금을
기다리고, 삭제가 커밋되면 UPDATE는 0행이 된다. 이때 SQLAlchemy StaleDataError 같은 내부
예외가 새어 나오면 안 되고 UserNotFoundError -> AuthenticationError(LOGIN_FAILED)여야 한다.
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import LOGIN_FAILED
from app.domain.auth.credentials import Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from tests.factories import NOW
from tests.fakes.auth_stack import build_auth_stack
from tests.fakes.unit_of_work import FixedClock
from tests.support.auth_seed import seed_directory, seed_user
from tests.support.gated_uow import gated

if TYPE_CHECKING:
    from tests.integration.conftest import RealAuth

pytestmark = pytest.mark.integration

SETTLE = 0.7  # 로그인의 UPDATE가 삭제 쪽 행 잠금에서 기다리게 두는 시간
IP = "203.0.113.7"


async def test_login_blocked_on_the_row_lock_of_a_concurrent_delete_fails_as_login_failed(
    real_auth: RealAuth,
) -> None:
    await seed_directory(real_auth.uow_factory)
    target = await seed_user(real_auth.uow_factory, "kim", Role.SALES)
    reached, release = asyncio.Event(), asyncio.Event()
    login_factory = gated(
        real_auth.uow_factory, attribute="users", method="update", reached=reached, release=release
    )
    login = build_auth_stack(login_factory, FixedClock(NOW), real_auth.directory).login

    attempt = asyncio.create_task(
        login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)
    )
    await asyncio.wait_for(reached.wait(), timeout=10)  # 로그인이 사용자를 읽고 UPDATE 직전
    async with real_auth.uow_factory() as deleter:
        await deleter.users.delete(target.id)  # DELETE flush, 아직 미커밋
        release.set()
        await asyncio.sleep(SETTLE)  # 로그인 UPDATE가 삭제의 행 잠금에서 대기
        waiting = not attempt.done()
        await deleter.commit()

    outcome = (await asyncio.gather(attempt, return_exceptions=True))[0]

    assert waiting, "로그인 UPDATE가 삭제의 행 잠금을 기다리지 않아 경쟁이 재현되지 않았다"
    assert isinstance(outcome, AuthenticationError), repr(outcome)
    assert str(outcome) == LOGIN_FAILED
    async with real_auth.uow_factory() as uow:
        assert await uow.users.get_active_by_login_id(target.login_id) is None
