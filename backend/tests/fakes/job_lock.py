"""JobLock Port의 Fake(단일 프로세스).

같은 job 이름을 이미 잡고 있거나(`held_elsewhere`로 다른 프로세스가 잡은 것처럼 만든 경우 포함)
하면 기다리지 않고 False를 돌려준다. 잡았다 푼 기록(`acquired`, `released`)을 남기고,
`on_enter`는 잠금을 잡은 직후 한 번 불린다(잠금 안에서 일어나는 일을 흉내 낼 때 쓴다).
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterable


class FakeJobLock:
    def __init__(
        self,
        held_elsewhere: Iterable[str] = (),
        on_enter: Callable[[], None] | None = None,
    ) -> None:
        self.held_elsewhere = set(held_elsewhere)
        self.on_enter = on_enter
        self.acquired: list[str] = []
        self.released: list[str] = []
        self._held: set[str] = set()

    @asynccontextmanager
    async def try_hold(self, job: str) -> AsyncIterator[bool]:
        if job in self.held_elsewhere or job in self._held:
            yield False
            return
        self._held.add(job)
        self.acquired.append(job)
        try:
            if self.on_enter is not None:
                self.on_enter()
            yield True
        finally:
            self._held.discard(job)
            self.released.append(job)
