"""서버 시각 조회. Clock을 한 번만 읽어 now와 today가 항상 일치한다."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.common.business_date import business_time

if TYPE_CHECKING:
    from datetime import date, datetime

    from app.application.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class ServerTimeView:
    now: datetime
    today: date


class GetServerTime:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    async def execute(self) -> ServerTimeView:
        local = business_time(self._clock.now())
        return ServerTimeView(now=local, today=local.date())
