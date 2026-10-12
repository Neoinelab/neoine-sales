"""T-D11: 로그인 실패 카운터 규칙(THR-1·3). 불변 객체이고 record_failure는 새 객체를 돌려준다."""

from datetime import timedelta
from typing import TYPE_CHECKING

from app.domain.auth.errors import TooManyAttemptsError
from app.domain.common.errors import DomainError
from tests.factories import NOW
from tests.factories_auth import make_counter, make_policy

if TYPE_CHECKING:
    from app.domain.auth.login_failure import FailureCounter

MINUTE = timedelta(minutes=1)


def _fail_n_times(times: int) -> FailureCounter:
    counter = make_counter()
    policy = make_policy()
    for index in range(times):
        counter = counter.record_failure(NOW + index * MINUTE, policy)
    return counter


def test_fresh_counter_is_not_locked() -> None:
    assert not make_counter().is_locked(NOW)


def test_failures_below_the_limit_do_not_lock() -> None:
    counter = _fail_n_times(4)

    assert counter.failures == 4
    assert not counter.is_locked(NOW + 4 * MINUTE)


def test_failure_reaching_the_limit_locks_for_the_lock_duration() -> None:
    counter = _fail_n_times(5)
    locked_at = NOW + 4 * MINUTE

    assert counter.is_locked(locked_at)
    assert counter.locked_until == locked_at + timedelta(minutes=15)


def test_lock_lasts_until_exactly_the_lock_end() -> None:
    counter = _fail_n_times(5)
    locked_until = counter.locked_until
    assert locked_until is not None

    assert counter.is_locked(locked_until - timedelta(seconds=1))
    assert not counter.is_locked(locked_until)


def test_record_failure_does_not_mutate_the_original() -> None:
    original = make_counter()

    updated = original.record_failure(NOW, make_policy())

    assert original.failures == 0
    assert updated.failures == 1
    assert updated.key == original.key


def test_first_failure_starts_the_window() -> None:
    later_time = NOW + 3 * MINUTE

    counter = make_counter().record_failure(later_time, make_policy())

    assert counter.failures == 1
    assert counter.window_started_at == later_time


def test_failures_inside_the_window_accumulate_without_moving_the_window() -> None:
    policy = make_policy()
    counter = make_counter().record_failure(NOW, policy)

    counter = counter.record_failure(NOW + timedelta(minutes=14, seconds=59), policy)

    assert counter.failures == 2
    assert counter.window_started_at == NOW


def test_failure_after_the_window_restarts_counting() -> None:
    policy = make_policy()
    counter = make_counter()
    for index in range(4):
        counter = counter.record_failure(NOW + index * MINUTE, policy)
    after_window = NOW + timedelta(minutes=15)

    counter = counter.record_failure(after_window, policy)

    assert counter.failures == 1
    assert counter.window_started_at == after_window
    assert not counter.is_locked(after_window)


def test_failure_after_the_lock_expired_restarts_counting() -> None:
    policy = make_policy()
    counter = make_counter()
    for index in range(5):
        counter = counter.record_failure(NOW + index * MINUTE, policy)
    after_lock = NOW + timedelta(minutes=4 + 15)

    counter = counter.record_failure(after_lock, policy)

    assert counter.failures == 1
    assert not counter.is_locked(after_lock)


def test_policy_limit_is_configurable() -> None:
    policy = make_policy(max_failures=2, lock_duration=timedelta(minutes=30))
    counter = make_counter().record_failure(NOW, policy).record_failure(NOW, policy)

    assert counter.is_locked(NOW + timedelta(minutes=29))
    assert not counter.is_locked(NOW + timedelta(minutes=30))


def test_policy_window_is_configurable() -> None:
    policy = make_policy(window=timedelta(minutes=5))
    counter = make_counter().record_failure(NOW, policy)

    counter = counter.record_failure(NOW + timedelta(minutes=5), policy)

    assert counter.failures == 1


def test_too_many_attempts_is_a_domain_error() -> None:
    assert issubclass(TooManyAttemptsError, DomainError)
