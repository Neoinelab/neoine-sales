"""병렬 요청으로 로그인 시도 제한을 우회할 수 없다(THR-2, 리뷰 Major 1).

AD 호출 전에 같은 트랜잭션에서 시도를 선점(선반영)해야 하므로, 디렉터리 응답이 느려도
병렬 N건이 한도를 넘는 AD 호출을 만들 수 없다. 성공·연결 장애로 끝난 시도는 되돌려진다.
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from app.domain.auth.credentials import Password
from app.domain.auth.errors import AuthenticationError, TooManyAttemptsError
from app.domain.auth.principal import Role
from tests.factories_auth import WRONG_PASSWORD, make_directory_settings
from tests.fakes.admin_stack import ADMIN_ACTOR, ADMIN_PASSWORD
from tests.fakes.auth_stack import MAX_PER_ACCOUNT, MAX_PER_IP
from tests.support.auth_seed import account_key, ip_key, seed_directory, seed_user

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.directory import FakeDirectoryAuthenticator
    from tests.fakes.unit_of_work import FakeUnitOfWork

IP = "10.0.0.1"
PARALLEL = 20
CANDIDATE = make_directory_settings(base_dn="dc=new,dc=test")
DIRECTORY_DELAY = 0.05


@pytest.fixture(autouse=True)
async def _slow_directory(
    uow_factory: UnitOfWorkFactory, directory: FakeDirectoryAuthenticator
) -> None:
    """AD 응답이 느린 상황(경쟁 창)을 만든다. kim 사용자와 AD 설정을 준비한다."""
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)

    async def delay() -> None:
        await asyncio.sleep(DIRECTORY_DELAY)

    directory.on_authenticate = delay


def _too_many(results: Sequence[object]) -> int:
    return sum(isinstance(r, TooManyAttemptsError) for r in results)


async def test_parallel_wrong_passwords_call_the_directory_at_most_the_account_limit(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    results = await asyncio.gather(
        *(
            auth.login.execute(login_id="kim", password=Password(WRONG_PASSWORD), client_ip=IP)
            for _ in range(PARALLEL)
        ),
        return_exceptions=True,
    )

    assert len(directory.authenticate_calls) <= MAX_PER_ACCOUNT
    assert all(isinstance(r, AuthenticationError | TooManyAttemptsError) for r in results)
    assert _too_many(results) >= PARALLEL - MAX_PER_ACCOUNT


async def test_parallel_wrong_passwords_lock_the_account_for_a_correct_password(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    await asyncio.gather(
        *(
            auth.login.execute(login_id="kim", password=Password(WRONG_PASSWORD), client_ip=IP)
            for _ in range(PARALLEL)
        ),
        return_exceptions=True,
    )
    calls = len(directory.authenticate_calls)

    with pytest.raises(TooManyAttemptsError):
        await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    assert len(directory.authenticate_calls) == calls


async def test_parallel_attempts_across_accounts_respect_the_ip_limit(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    attempts = MAX_PER_IP * 2

    results = await asyncio.gather(
        *(
            auth.login.execute(
                login_id=f"user{number}", password=Password(WRONG_PASSWORD), client_ip=IP
            )
            for number in range(attempts)
        ),
        return_exceptions=True,
    )

    assert len(directory.authenticate_calls) <= MAX_PER_IP
    assert _too_many(results) >= attempts - MAX_PER_IP


async def test_parallel_first_admin_setup_attempts_respect_the_account_limit(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    """kim은 admin이 아니므로 최초 설정은 아직 열려 있다."""
    results = await asyncio.gather(
        *(
            auth.setup_admin.execute(
                login_id="kim", password=Password(WRONG_PASSWORD), client_ip=IP
            )
            for _ in range(PARALLEL)
        ),
        return_exceptions=True,
    )

    assert len(directory.authenticate_calls) <= MAX_PER_ACCOUNT
    assert _too_many(results) >= PARALLEL - MAX_PER_ACCOUNT


async def test_parallel_settings_checks_respect_the_account_limit(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    results = await asyncio.gather(
        *(
            admin.test_settings.execute(
                actor=ADMIN_ACTOR,
                settings=CANDIDATE,
                password=Password(WRONG_PASSWORD),
                client_ip=IP,
            )
            for _ in range(PARALLEL)
        ),
        return_exceptions=True,
    )

    assert len(directory.authenticate_calls) <= MAX_PER_ACCOUNT
    assert _too_many(results) >= PARALLEL - MAX_PER_ACCOUNT


async def test_successful_logins_do_not_consume_the_ip_limit(auth: AuthStack) -> None:
    for _ in range(MAX_PER_IP + 1):
        await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)


async def test_successful_login_leaves_no_failure_on_either_counter(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    counters = uow.login_failures._items
    assert counters.get(account_key("kim")) is None
    assert counters.get(ip_key(IP)) is None or counters[ip_key(IP)].failures == 0


async def test_directory_outages_do_not_consume_the_ip_limit(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    directory.fail_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)
    for _ in range(MAX_PER_IP + 1):
        with pytest.raises(DirectoryUnavailableError):
            await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)
    directory.fail_with = None

    await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)


async def test_successful_settings_checks_give_back_their_reserved_attempt(
    admin: AdminStack,
) -> None:
    for _ in range(MAX_PER_ACCOUNT - 2):
        await _check(admin, WRONG_PASSWORD)
    for _ in range(MAX_PER_ACCOUNT):
        await _check(admin, ADMIN_PASSWORD)  # 성공은 시도를 소모하지 않는다

    result = await _check(admin, WRONG_PASSWORD)  # 한도 직전의 실패는 여전히 AD까지 간다

    assert result.success is False  # type: ignore[attr-defined]


async def _check(admin: AdminStack, password: str) -> object:
    return await admin.test_settings.execute(
        actor=ADMIN_ACTOR, settings=CANDIDATE, password=Password(password), client_ip=IP
    )
