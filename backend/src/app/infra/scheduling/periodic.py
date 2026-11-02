"""주기 실행기: 시작하자마자 한 번, 이후 일정 간격마다 작업을 실행한다."""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class PeriodicTask:
    def __init__(
        self,
        run_once: Callable[[], Awaitable[object]],
        interval_seconds: float,
        *,
        name: str,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if interval_seconds <= 0:
            msg = "interval_seconds는 0보다 커야 합니다"
            raise ValueError(msg)
        self._run_once = run_once
        self._interval = interval_seconds
        self._name = name
        self._sleep = sleep

    async def run_forever(self) -> None:
        """즉시 1회 실행하고 interval마다 반복한다. 오류는 기록하고 계속하며 취소는 전파한다."""
        while True:
            try:
                await self._run_once()
            except Exception:
                logger.exception("주기 작업 실패(다음 주기에 다시 시도): %s", self._name)
            await self._sleep(self._interval)
