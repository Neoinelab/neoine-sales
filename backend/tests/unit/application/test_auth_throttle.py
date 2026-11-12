"""로그인 시도 제한(THR-1~5, T-U7~U11). 키는 HMAC 해시이고 카운터는 UoW에 커밋돼야 한다."""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError, TooManyAttemptsError
from app.domain.auth.principal import Role
from tests.fakes.auth_stack import LOCK, MAX_PER_ACCOUNT, MAX_PER_IP, WINDOW, build_auth_stack
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
    """한 아이디가 한도만큼 실패하면 올바른 비밀번호도 잠기고 AD를 부르지 않는다.

    테스트 코드: AU-042
    """
    # given: kim이 틀린 비밀번호로 5번 실패했다
    await _fail(auth, times=MAX_PER_ACCOUNT)
    calls_before = len(directory.authenticate_calls)

    # when: 올바른 비밀번호로 로그인한다
    with pytest.raises(TooManyAttemptsError):
        await _succeed(auth)  # 올바른 비밀번호여도 잠겨 있다

    # then: 429이고 AD를 더 부르지 않았다
    assert len(directory.authenticate_calls) == calls_before


async def test_failures_below_the_limit_do_not_lock(auth: AuthStack) -> None:
    """한도보다 한 번 적게 실패하면 잠기지 않는다.

    테스트 코드: AU-043
    """
    # given: kim이 4번 실패했다
    await _fail(auth, times=MAX_PER_ACCOUNT - 1)

    # when·then: 올바른 비밀번호로 로그인한다 → 로그인된다(예외 없음)
    await _succeed(auth)


async def test_lock_applies_to_that_account_only(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """잠금은 그 아이디에만 걸린다.

    테스트 코드: AU-044
    """
    # given: kim이 잠겼고 lee는 정상이다
    await seed_user(uow_factory, "lee", Role.SALES)
    auth.directory.add_account("lee", "pw-lee")
    await _fail(auth, times=MAX_PER_ACCOUNT)

    # when: lee가 로그인한다
    outcome = await auth.login.execute(login_id="lee", password=Password("pw-lee"), client_ip=IP)

    # then: lee는 로그인된다
    assert outcome.session.principal.subject == "lee"


async def test_lock_ends_exactly_after_the_lock_duration(
    auth: AuthStack, clock: FixedClock
) -> None:
    """잠금은 잠금 시간이 정확히 지나면 풀린다.

    테스트 코드: AU-045
    """
    # given: kim이 잠겼다
    await _fail(auth, times=MAX_PER_ACCOUNT)

    # when: 잠금 끝 1초 전에는 잠겨 있고 정확히 끝 시각이 되면
    clock.advance(LOCK_SECONDS - 1)
    with pytest.raises(TooManyAttemptsError):
        # then: 풀려 로그인된다
        await _succeed(auth)
    clock.advance(1)

    await _succeed(auth)


async def test_failure_window_expiry_restarts_the_count(auth: AuthStack, clock: FixedClock) -> None:
    """실패 창이 지나면 실패 횟수를 처음부터 다시 센다.

    테스트 코드: AU-046
    """
    # given: kim이 4번 실패하고 실패 창 길이만큼 시간이 지났다
    await _fail(auth, times=MAX_PER_ACCOUNT - 1)
    clock.advance(WINDOW_SECONDS)

    # when: 다시 4번 실패한다
    await _fail(auth, times=MAX_PER_ACCOUNT - 1)

    # then: 5번째 시도는 잠기지 않고 로그인된다
    await _succeed(auth)


async def test_success_clears_the_account_counter(auth: AuthStack, uow: FakeUnitOfWork) -> None:
    """로그인에 성공하면 아이디 카운터가 지워지고 다시 센다.

    테스트 코드: AU-047
    """
    # given: kim이 4번 실패해 카운터가 있다
    await _fail(auth, times=MAX_PER_ACCOUNT - 1)
    assert account_key("kim") in uow.login_failures._items

    # when: 올바른 비밀번호로 로그인한다
    await _succeed(auth)

    # then: 카운터가 지워져 다시 4번까지는 잠기지 않는다
    assert account_key("kim") not in uow.login_failures._items
    await _fail(auth, times=MAX_PER_ACCOUNT - 1)
    await _succeed(auth)  # 초기화됐으므로 다시 4회까지는 잠기지 않는다


async def test_unknown_login_ids_are_throttled_the_same_way(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    """없는 아이디도 같은 방식으로 제한된다.

    테스트 코드: AU-049
    """
    # given: 없는 아이디 ghost가 한도만큼 실패했다
    await _fail(auth, "ghost", times=MAX_PER_ACCOUNT)
    calls_before = len(directory.authenticate_calls)

    # when: ghost로 다시 로그인한다
    with pytest.raises(TooManyAttemptsError):
        await auth.login.execute(login_id="ghost", password=Password("x"), client_ip=IP)

    # then: 429이고 AD를 부르지 않았다
    assert len(directory.authenticate_calls) == calls_before


async def test_unregistered_directory_user_counts_as_a_failure(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """AD에는 있지만 등록되지 않은 아이디의 로그인도 실패로 센다.

    테스트 코드: AU-049
    """
    # given: AD에만 있는 newbie
    auth.directory.add_account("newbie", "pw-newbie")

    # when: newbie가 로그인한다
    with pytest.raises(AuthenticationError):
        await auth.login.execute(login_id="newbie", password=Password("pw-newbie"), client_ip=IP)

    # then: 실패가 1회 센다
    assert uow.login_failures._items[account_key("newbie")].failures == 1


async def test_ip_is_locked_after_its_limit_across_different_accounts(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    """한 IP에서 서로 다른 아이디로 한도만큼 실패하면 다른 아이디도 잠긴다.

    테스트 코드: AU-048
    """
    # given: 한 IP에서 서로 다른 아이디로 30번 실패했다
    for number in range(MAX_PER_IP):
        await _fail(auth, f"user{number}")
    calls_before = len(directory.authenticate_calls)

    # when: 같은 IP에서 kim이 로그인한다
    with pytest.raises(TooManyAttemptsError):
        await _succeed(auth)  # 이 IP에서는 새 계정도 거부된다

    # then: 429이고 AD를 부르지 않았으며 다른 IP는 영향이 없다
    assert len(directory.authenticate_calls) == calls_before
    await _succeed(auth, ip="10.0.0.2")  # 다른 IP는 영향이 없다


async def test_directory_outage_without_a_stored_hash_counts_toward_the_limit(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    """AD 장애 중 대체 실패도 일반 실패와 같게 세어 한도에 이르면 429다.

    테스트 코드: AU-051
    """
    # given: AD 연결 불가이고 kim에게 해시가 없다
    directory.fail_all_with(DirectoryUnavailableError(stage=VerificationStage.CONNECT))
    # when: 대체 로그인 실패를 한도만큼 한다
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(DirectoryUnavailableError):
            await _succeed(auth)

    # then: 다음 시도는 429다
    with pytest.raises(TooManyAttemptsError):
        await _succeed(auth)


async def test_counter_keys_are_keyed_hashes_not_raw_values(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """카운터 키는 비밀 기반 해시이고 원본 아이디·IP가 없다.

    테스트 코드: AU-050
    """
    # when: kim이 한 번 실패한다
    await _fail(auth)

    # then: 키는 아이디·IP의 HMAC 해시 둘뿐이고 원본이 없다
    keys = set(uow.login_failures._items)
    assert keys == {account_key("kim"), ip_key(IP)}
    assert all(len(key) == 64 for key in keys)
    assert not any("kim" in key or "10.0.0.1" in key for key in keys)
    counters = uow.login_failures._items
    assert counters[account_key("kim")].failures == 1
    assert counters[ip_key(IP)].failures == 1


async def test_throttle_methods_lock_and_clear_by_login_id(auth: AuthStack) -> None:
    """시도 제한 유스케이스의 기록·확인·초기화가 아이디 기준으로 동작한다."""
    login_id = LoginId("kim")
    # when: 아이디의 실패를 한도만큼 기록하고
    for _ in range(MAX_PER_ACCOUNT):
        await auth.throttle.record_failure(login_id, IP)

    # then: 확인하면 잠겨 있고 초기화하면 풀린다
    with pytest.raises(TooManyAttemptsError):
        await auth.throttle.ensure_allowed(login_id, IP)
    await auth.throttle.clear(login_id)

    await auth.throttle.ensure_allowed(login_id, "10.9.9.9")


async def test_successful_logins_do_not_consume_the_ip_limit(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """로그인 성공은 IP 한도를 쓰지 않아 한도보다 많이 연달아 성공한다.

    테스트 코드: AU-047
    """
    # when: 같은 IP에서 IP 한도보다 한 번 많이 연달아 로그인에 성공한다
    #   (전제: AD 계정이 있는 등록된 kim (fixture))
    for _ in range(MAX_PER_IP + 1):
        await _succeed(auth)

    # then: 한 번도 429가 아니었고, 이어진 실패 한 번이 IP 카운터에 1회로만 남는다
    await _fail(auth)
    assert uow.login_failures._items[ip_key(IP)].failures == 1


async def test_failure_counters_are_shared_between_app_instances(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """한 서버 인스턴스에서 쌓인 실패 횟수가 같은 저장소를 보는 다른 인스턴스에서도 계정을 잠근다.

    테스트 코드: AU-050
    """
    # given: 첫 인스턴스에서 kim이 한도만큼 실패했고, 같은 저장소를 보는 두 번째 인스턴스가 있다
    await _fail(auth, times=MAX_PER_ACCOUNT)
    other = build_auth_stack(uow_factory, clock)
    other.directory.add_account("kim", "pw-kim")

    # when: 두 번째 인스턴스에서 올바른 비밀번호로 로그인한다
    with pytest.raises(TooManyAttemptsError):
        await other.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    # then: 429이고 두 번째 인스턴스의 AD를 부르지 않았다
    assert other.directory.authenticate_calls == []
