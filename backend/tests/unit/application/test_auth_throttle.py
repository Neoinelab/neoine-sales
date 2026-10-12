"""로그인 시도 제한(THR-1~5, T-U7~U11). 키는 HMAC 해시이고 카운터는 UoW에 커밋돼야 한다."""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError, TooManyAttemptsError
from app.domain.auth.principal import Role
from tests.fakes.auth_stack import LOCK, MAX_PER_ACCOUNT, MAX_PER_IP, WINDOW
from tests.support.auth_seed import account_key, ip_key, seed_directory, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.directory import FakeDirectoryAuthenticator
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

IP = "10.0.0.1"
LOCK_SECONDS = int(LOCK.total_seconds())
WINDOW_SECONDS = int(WINDOW.total_seconds())


@pytest.fixture(autouse=True)
async def _ready(uow_factory: UnitOfWorkFactory) -> None:
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)


async def _fail(auth: AuthStack, login_id: str = "kim", ip: str = IP, times: int = 1) -> None:
    for _ in range(times):
        with pytest.raises(AuthenticationError):
            await auth.login.execute(login_id=login_id, password=Password("wrong"), client_ip=ip)


async def _succeed(auth: AuthStack, ip: str = IP) -> None:
    await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=ip)


async def test_account_is_locked_after_the_limit_without_calling_the_directory(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    await _fail(auth, times=MAX_PER_ACCOUNT)
    calls_before = len(directory.authenticate_calls)

    with pytest.raises(TooManyAttemptsError):
        await _succeed(auth)  # 올바른 비밀번호여도 잠겨 있다

    assert len(directory.authenticate_calls) == calls_before


async def test_failures_below_the_limit_do_not_lock(auth: AuthStack) -> None:
    await _fail(auth, times=MAX_PER_ACCOUNT - 1)

    await _succeed(auth)


async def test_lock_applies_to_that_account_only(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "lee", Role.SALES)
    auth.directory.add_account("lee", "pw-lee")
    await _fail(auth, times=MAX_PER_ACCOUNT)

    issued = await auth.login.execute(login_id="lee", password=Password("pw-lee"), client_ip=IP)

    assert issued.principal.subject == "lee"


async def test_lock_ends_exactly_after_the_lock_duration(
    auth: AuthStack, clock: FixedClock
) -> None:
    await _fail(auth, times=MAX_PER_ACCOUNT)

    clock.advance(LOCK_SECONDS - 1)
    with pytest.raises(TooManyAttemptsError):
        await _succeed(auth)
    clock.advance(1)

    await _succeed(auth)


async def test_failure_window_expiry_restarts_the_count(auth: AuthStack, clock: FixedClock) -> None:
    await _fail(auth, times=MAX_PER_ACCOUNT - 1)
    clock.advance(WINDOW_SECONDS)

    await _fail(auth, times=MAX_PER_ACCOUNT - 1)

    await _succeed(auth)


async def test_success_clears_the_account_counter(auth: AuthStack, uow: FakeUnitOfWork) -> None:
    await _fail(auth, times=MAX_PER_ACCOUNT - 1)
    assert account_key("kim") in uow.login_failures._items

    await _succeed(auth)

    assert account_key("kim") not in uow.login_failures._items
    await _fail(auth, times=MAX_PER_ACCOUNT - 1)
    await _succeed(auth)  # 초기화됐으므로 다시 4회까지는 잠기지 않는다


async def test_unknown_login_ids_are_throttled_the_same_way(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    await _fail(auth, "ghost", times=MAX_PER_ACCOUNT)
    calls_before = len(directory.authenticate_calls)

    with pytest.raises(TooManyAttemptsError):
        await auth.login.execute(login_id="ghost", password=Password("x"), client_ip=IP)

    assert len(directory.authenticate_calls) == calls_before


async def test_unregistered_directory_user_counts_as_a_failure(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    auth.directory.add_account("newbie", "pw-newbie")

    with pytest.raises(AuthenticationError):
        await auth.login.execute(login_id="newbie", password=Password("pw-newbie"), client_ip=IP)

    assert uow.login_failures._items[account_key("newbie")].failures == 1


async def test_ip_is_locked_after_its_limit_across_different_accounts(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    for number in range(MAX_PER_IP):
        await _fail(auth, f"user{number}")
    calls_before = len(directory.authenticate_calls)

    with pytest.raises(TooManyAttemptsError):
        await _succeed(auth)  # 이 IP에서는 새 계정도 거부된다

    assert len(directory.authenticate_calls) == calls_before
    await _succeed(auth, ip="10.0.0.2")  # 다른 IP는 영향이 없다


async def test_directory_outage_does_not_count_toward_the_limit(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    directory.fail_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)
    for _ in range(MAX_PER_ACCOUNT + 1):
        with pytest.raises(DirectoryUnavailableError):
            await _succeed(auth)
    directory.fail_with = None

    await _succeed(auth)


async def test_counter_keys_are_keyed_hashes_not_raw_values(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    await _fail(auth)

    keys = set(uow.login_failures._items)
    assert keys == {account_key("kim"), ip_key(IP)}
    assert all(len(key) == 64 for key in keys)
    assert not any("kim" in key or "10.0.0.1" in key for key in keys)
    counters = uow.login_failures._items
    assert counters[account_key("kim")].failures == 1
    assert counters[ip_key(IP)].failures == 1


async def test_throttle_methods_lock_and_clear_by_login_id(auth: AuthStack) -> None:
    login_id = LoginId("kim")
    for _ in range(MAX_PER_ACCOUNT):
        await auth.throttle.record_failure(login_id, IP)

    with pytest.raises(TooManyAttemptsError):
        await auth.throttle.ensure_allowed(login_id, IP)
    await auth.throttle.clear(login_id)

    await auth.throttle.ensure_allowed(login_id, "10.9.9.9")
