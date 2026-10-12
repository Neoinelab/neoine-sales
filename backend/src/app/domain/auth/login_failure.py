from dataclasses import dataclass, replace
from datetime import datetime, timedelta  # noqa: TC003 (dataclass 필드 타입)


@dataclass(frozen=True, slots=True)
class FailurePolicy:
    max_failures: int
    window: timedelta
    lock_duration: timedelta


@dataclass(frozen=True, slots=True)
class FailureCounter:
    """키(아이디·IP의 해시)별 로그인 실패 기록. 불변이며 갱신은 새 객체를 돌려준다."""

    key: str
    failures: int
    window_started_at: datetime
    locked_until: datetime | None = None

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and now < self.locked_until

    def record_failure(self, now: datetime, policy: FailurePolicy) -> FailureCounter:
        if self.is_locked(now):
            return replace(self, failures=self.failures + 1)
        if self._is_stale(now, policy):
            counter = replace(self, failures=1, window_started_at=now, locked_until=None)
        else:
            counter = replace(self, failures=self.failures + 1)
        if counter.failures >= policy.max_failures:
            return replace(counter, locked_until=now + policy.lock_duration)
        return counter

    def release(self, policy: FailurePolicy) -> FailureCounter:
        """선점했던 시도 1회를 되돌린다. 한도 아래로 내려가면 잠금도 푼다."""
        counter = replace(self, failures=max(0, self.failures - 1))
        if counter.failures < policy.max_failures:
            return replace(counter, locked_until=None)
        return counter

    def _is_stale(self, now: datetime, policy: FailurePolicy) -> bool:
        return (
            self.failures == 0
            or self.locked_until is not None
            or now - self.window_started_at >= policy.window
        )
