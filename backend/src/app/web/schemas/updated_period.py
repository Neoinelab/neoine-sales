"""최종 업데이트 기간 프리셋 응답. 날짜는 서버 업무 날짜 기준이며 JSON 키는 from/to다."""

from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.domain.deal.updated_period import UpdatedPeriodPreset

if TYPE_CHECKING:
    from app.application.deal.updated_periods import UpdatedPeriodsView


class UpdatedPeriodResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: UpdatedPeriodPreset
    from_: date = Field(alias="from")
    to: date


class UpdatedPeriodsResponse(BaseModel):
    today: date
    periods: list[UpdatedPeriodResponse]

    @classmethod
    def from_view(cls, view: UpdatedPeriodsView) -> UpdatedPeriodsResponse:
        periods = [
            UpdatedPeriodResponse(key=p.preset, from_=p.start, to=p.end) for p in view.periods
        ]
        return cls(today=view.today, periods=periods)
