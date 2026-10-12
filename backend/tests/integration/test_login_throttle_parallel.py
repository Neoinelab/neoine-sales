"""실제 PostgreSQL에서의 로그인 시도 선점: 병렬 요청이 한도를 넘어 AD를 호출하지 못한다 (THR-2).

카운터 행이 아직 없는 첫 병렬 요청들도 서로 직렬화되어야 하고(행 선생성 + FOR UPDATE 등),
성공한 시도는 되돌려져야 한다.
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError, TooManyAttemptsError
from app.domain.auth.login_failure import FailureCounter
from app.domain.auth.principal import Role
from tests.factories import NOW
from tests.factories_auth import WRONG_PASSWORD
from tests.fakes.auth_stack import MAX_PER_ACCOUNT, MAX_PER_IP
from tests.support.auth_seed import account_key, ip_key, seed_directory, seed_user

if TYPE_CHECKING:
    from tests.integration.conftest import RealAuth

pytestmark = pytest.mark.integration
IP = "10.0.0.1"
PARALLEL = 20
DELAY = 0.1
WAIT = 0.5


@pytest.fixture
async def ready(real_auth: RealAuth) -> RealAuth:
    await seed_directory(real_auth.uow_factory)
    await seed_user(real_auth.uow_factory, "kim", Role.SALES)

    async def slow() -> None:
        await asyncio.sleep(DELAY)

    real_auth.directory.on_authenticate = slow
    return real_auth


async def _failures(real: RealAuth, key: str) -> int:
    async with real.uow_factory() as uow:
        counter = await uow.login_failures.get_for_update(key)
    return 0 if counter is None else counter.failures


async def test_parallel_wrong_passwords_call_the_directory_at_most_the_account_limit(
    ready: RealAuth,
) -> None:
    results = await asyncio.gather(
        *(
            ready.stack.login.execute(
                login_id="kim", password=Password(WRONG_PASSWORD), client_ip=IP
            )
            for _ in range(PARALLEL)
        ),
        return_exceptions=True,
    )

    assert len(ready.directory.authenticate_calls) <= MAX_PER_ACCOUNT
    assert all(isinstance(r, AuthenticationError | TooManyAttemptsError) for r in results)
    assert sum(isinstance(r, TooManyAttemptsError) for r in results) >= PARALLEL - MAX_PER_ACCOUNT


async def test_parallel_attempts_across_accounts_respect_the_ip_limit(ready: RealAuth) -> None:
    attempts = MAX_PER_IP * 2

    await asyncio.gather(
        *(
            ready.stack.login.execute(
                login_id=f"user{number}", password=Password(WRONG_PASSWORD), client_ip=IP
            )
            for number in range(attempts)
        ),
        return_exceptions=True,
    )

    assert len(ready.directory.authenticate_calls) <= MAX_PER_IP


async def test_parallel_first_admin_setup_attempts_respect_the_account_limit(
    ready: RealAuth,
) -> None:
    await asyncio.gather(
        *(
            ready.stack.setup_admin.execute(
                login_id="kim", password=Password(WRONG_PASSWORD), client_ip=IP
            )
            for _ in range(PARALLEL)
        ),
        return_exceptions=True,
    )

    assert len(ready.directory.authenticate_calls) <= MAX_PER_ACCOUNT


async def test_parallel_throttle_reservations_admit_at_most_the_account_limit(
    ready: RealAuth,
) -> None:
    """카운터 행이 없는 상태에서 동시에 예약해도 한도(5)만큼만 통과한다."""
    results = await asyncio.gather(
        *(ready.stack.throttle.ensure_allowed(LoginId("kim"), IP) for _ in range(PARALLEL)),
        return_exceptions=True,
    )

    admitted = [r for r in results if not isinstance(r, BaseException)]
    assert 1 <= len(admitted) <= MAX_PER_ACCOUNT
    assert all(isinstance(r, TooManyAttemptsError) for r in results if isinstance(r, BaseException))


async def test_a_reader_of_a_missing_counter_waits_for_the_writer_to_finish(
    ready: RealAuth,
) -> None:
    """같은 키의 카운터 행이 아직 없어도 두 번째 get_for_update는 첫 트랜잭션이 끝나길 기다린다."""
    key = account_key("ghost")

    async def second() -> int:
        async with ready.uow_factory() as uow:
            counter = await uow.login_failures.get_for_update(key)
            return 0 if counter is None else counter.failures

    async with ready.uow_factory() as first:
        assert await first.login_failures.get_for_update(key) is None
        waiter = asyncio.create_task(second())
        await asyncio.sleep(WAIT)
        waiting = not waiter.done()
        await first.login_failures.save(FailureCounter(key, 1, NOW))
        await first.commit()

    seen = await asyncio.wait_for(waiter, timeout=10)
    assert waiting, "행이 없을 때 두 번째 읽기가 잠기지 않으면 병렬 실패가 한 번으로 덮어써진다"
    assert seen == 1


async def test_successful_login_gives_back_the_reserved_attempt(ready: RealAuth) -> None:
    await ready.stack.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    assert await _failures(ready, account_key("kim")) == 0
    assert await _failures(ready, ip_key(IP)) == 0


async def test_successful_logins_do_not_consume_the_ip_limit(ready: RealAuth) -> None:
    ready.directory.on_authenticate = None
    for _ in range(MAX_PER_IP + 1):
        await ready.stack.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)
