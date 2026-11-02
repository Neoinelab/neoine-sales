from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager


class JobLock(Protocol):
    """작업 단위 배타 잠금 Port. 여러 프로세스 중 한 곳만 작업을 하게 한다."""

    def try_hold(self, job: str) -> AbstractAsyncContextManager[bool]:
        """기다리지 않고 잠금을 시도한다. 잡으면 True(블록을 나갈 때 해제), 다른 곳이 쥐면 False."""
        ...
