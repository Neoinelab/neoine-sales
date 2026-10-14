"""로그인의 사용자 갱신 직후 행이 물리 삭제돼도 세션 발급은 500이 아니라 LOGIN_FAILED로 끝난다.

리뷰 Minor 1. 로그인이 last-login을 커밋한 뒤 세션 INSERT 직전에 다른 요청이 사용자를 물리
삭제하면 auth_sessions.user_id FK가 위반된다. SessionRepository.add가 이를 UserNotFoundError로
바꾸고 DirectoryLogin이 AuthenticationError(LOGIN_FAILED)로 바꿔야 한다(원시 IntegrityError 금지).
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

IP = "203.0.113.8"


async def test_login_whose_user_is_deleted_before_the_session_insert_fails_as_login_failed(
    real_auth: RealAuth,
) -> None:
    await seed_directory(real_auth.uow_factory)
    target = await seed_user(real_auth.uow_factory, "kim", Role.SALES)
    reached, release = asyncio.Event(), asyncio.Event()
    login_factory = gated(
        real_auth.uow_factory, attribute="sessions", method="add", reached=reached, release=release
    )
    login = build_auth_stack(login_factory, FixedClock(NOW), real_auth.directory).login

    attempt = asyncio.create_task(
        login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)
    )
    await asyncio.wait_for(reached.wait(), timeout=10)  # last-login 커밋 완료, 세션 INSERT 직전
    async with real_auth.uow_factory() as deleter:
        await deleter.users.delete(target.id)
        await deleter.commit()
    release.set()

    outcome = (await asyncio.gather(attempt, return_exceptions=True))[0]

    assert isinstance(outcome, AuthenticationError), repr(outcome)
    assert str(outcome) == LOGIN_FAILED
    async with real_auth.uow_factory() as uow:
        assert await uow.users.get_active_by_login_id(target.login_id) is None
