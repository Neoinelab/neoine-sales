"""최종 업데이트·Action 검색 기간 프리셋 응답.

날짜는 서버 업무 날짜 기준이며 JSON 키는 from/to다.
"""

from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.domain.deal.updated_period import UpcomingPeriodPreset, UpdatedPeriodPreset

if TYPE_CHECKING:
    from app.application.deal.updated_periods import UpdatedPeriodsView


class UpdatedPeriodResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: UpdatedPeriodPreset
    from_: date = Field(alias="from")
    to: date


class UpcomingPeriodResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: UpcomingPeriodPreset
    from_: date = Field(alias="from")
    to: date


class UpdatedPeriodsResponse(BaseModel):
    today: date
    periods: list[UpdatedPeriodResponse]
    upcoming: list[UpcomingPeriodResponse]

    @classmethod
    def from_view(cls, view: UpdatedPeriodsView) -> UpdatedPeriodsResponse:
        periods = [
            UpdatedPeriodResponse(key=p.preset, from_=p.start, to=p.end) for p in view.periods
        ]
        upcoming = [
            UpcomingPeriodResponse(key=u.preset, from_=u.start, to=u.end) for u in view.upcoming
        ]
        return cls(today=view.today, periods=periods, upcoming=upcoming)
