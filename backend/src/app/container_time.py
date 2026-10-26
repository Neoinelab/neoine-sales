"""서버 시각 유스케이스 조립 Container 부분(길이 분리)."""

from typing import TYPE_CHECKING

from app.application.time.get_server_time import GetServerTime

if TYPE_CHECKING:
    from app.application.ports.clock import Clock


class TimeUseCases:
    _clock: Clock

    def get_server_time(self) -> GetServerTime:
        return GetServerTime(self._clock)
