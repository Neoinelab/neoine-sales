"""로그인 실패 카운터 규칙(THR-1·3). 불변 객체이고 record_failure는 새 객체를 돌려준다."""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

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
    """새 카운터는 잠겨 있지 않다."""
    # when: 새 카운터가 잠겼는지 묻는다
    locked = make_counter().is_locked(NOW)

    # then: 잠겨 있지 않다
    assert not locked


def test_failures_below_the_limit_do_not_lock() -> None:
    """한도 미만의 실패는 잠그지 않는다."""
    # when: 한도보다 적은 4번 실패한다
    counter = _fail_n_times(4)

    # then: 실패 4회가 기록되고 잠기지 않는다
    assert counter.failures == 4
    assert not counter.is_locked(NOW + 4 * MINUTE)


def test_failure_reaching_the_limit_locks_for_the_lock_duration() -> None:
    """한도에 도달한 실패는 잠금 시간만큼 잠근다."""
    # when: 한도인 5번 실패한다
    counter = _fail_n_times(5)
    locked_at = NOW + 4 * MINUTE

    # then: 마지막 실패 시각부터 15분간 잠긴다
    assert counter.is_locked(locked_at)
    assert counter.locked_until == locked_at + timedelta(minutes=15)


def test_lock_lasts_until_exactly_the_lock_end() -> None:
    """잠금은 잠금 종료 시각 직전까지 유지되고 그 시각에 풀린다."""
    # given: 한도까지 실패해 잠긴 카운터
    counter = _fail_n_times(5)
    locked_until = counter.locked_until or pytest.fail("잠금 종료 시각이 없다")

    # when: 종료 1초 전과 종료 시각에 잠금을 판정한다
    result_1 = counter.is_locked(locked_until - timedelta(seconds=1))
    result_2 = counter.is_locked(locked_until)
    # then: 1초 전에는 잠겨 있고 종료 시각에는 풀려 있다
    assert result_1
    assert not result_2


def test_record_failure_does_not_mutate_the_original() -> None:
    """실패를 기록해도 원래 카운터는 바뀌지 않는다."""
    # given: 새 카운터
    original = make_counter()

    # when: 실패를 기록한다
    updated = original.record_failure(NOW, make_policy())

    # then: 원본은 그대로이고 새 객체에 1회가 기록된다
    assert original.failures == 0
    assert updated.failures == 1
    assert updated.key == original.key


def test_first_failure_starts_the_window() -> None:
    """첫 실패는 그 시각에 집계 구간을 시작한다."""
    # given: 첫 실패 시각
    later_time = NOW + 3 * MINUTE

    # when: 첫 실패를 기록한다
    counter = make_counter().record_failure(later_time, make_policy())

    # then: 실패 1회이고 구간이 그 시각에 시작한다
    assert counter.failures == 1
    assert counter.window_started_at == later_time


def test_failures_inside_the_window_accumulate_without_moving_the_window() -> None:
    """구간 안의 실패는 누적되고 구간 시작은 움직이지 않는다."""
    # given: 첫 실패가 기록된 카운터
    policy = make_policy()
    counter = make_counter().record_failure(NOW, policy)

    # when: 구간이 끝나기 1초 전에 다시 실패한다
    counter = counter.record_failure(NOW + timedelta(minutes=14, seconds=59), policy)

    # then: 2회로 누적되고 구간 시작은 그대로다
    assert counter.failures == 2
    assert counter.window_started_at == NOW


def test_failure_after_the_window_restarts_counting() -> None:
    """구간이 지난 뒤의 실패는 처음부터 다시 센다."""
    # given: 구간 안에서 4번 실패한 카운터
    policy = make_policy()
    counter = make_counter()
    for index in range(4):
        counter = counter.record_failure(NOW + index * MINUTE, policy)
    after_window = NOW + timedelta(minutes=15)

    # when: 구간이 지난 시각에 실패한다
    counter = counter.record_failure(after_window, policy)

    # then: 1회부터 다시 세고 새 구간이 시작되며 잠기지 않는다
    assert counter.failures == 1
    assert counter.window_started_at == after_window
    assert not counter.is_locked(after_window)


def test_failure_after_the_lock_expired_restarts_counting() -> None:
    """잠금이 끝난 뒤의 실패는 처음부터 다시 센다."""
    # given: 5번 실패해 잠겼던 카운터
    policy = make_policy()
    counter = make_counter()
    for index in range(5):
        counter = counter.record_failure(NOW + index * MINUTE, policy)
    after_lock = NOW + timedelta(minutes=4 + 15)

    # when: 잠금이 끝난 시각에 실패한다
    counter = counter.record_failure(after_lock, policy)

    # then: 1회부터 다시 세고 잠기지 않는다
    assert counter.failures == 1
    assert not counter.is_locked(after_lock)


def test_policy_limit_is_configurable() -> None:
    """정책의 한도와 잠금 시간을 바꿀 수 있다."""
    # given: 한도 2회, 잠금 30분 정책
    policy = make_policy(max_failures=2, lock_duration=timedelta(minutes=30))

    # when: 2번 실패한다
    counter = make_counter().record_failure(NOW, policy).record_failure(NOW, policy)

    # then: 29분 뒤에도 잠겨 있고 30분 뒤에 풀린다
    assert counter.is_locked(NOW + timedelta(minutes=29))
    assert not counter.is_locked(NOW + timedelta(minutes=30))


def test_policy_window_is_configurable() -> None:
    """정책의 집계 구간 길이를 바꿀 수 있다."""
    # given: 구간 5분 정책과 첫 실패
    policy = make_policy(window=timedelta(minutes=5))
    counter = make_counter().record_failure(NOW, policy)

    # when: 5분 뒤에 다시 실패한다
    counter = counter.record_failure(NOW + timedelta(minutes=5), policy)

    # then: 구간이 지났으므로 1회부터 다시 센다
    assert counter.failures == 1


def test_too_many_attempts_is_a_domain_error() -> None:
    """TooManyAttemptsError는 DomainError의 하위 타입이다."""
    # when·then: 상속 관계를 확인한다
    assert issubclass(TooManyAttemptsError, DomainError)
