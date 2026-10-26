"""Deal 연도 선택지의 기준 응답. 화면이 이 값부터 올해+1까지 연도를 보여 준다."""

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.application.deal.deal_years import DealYearsView


class DealYearsResponse(BaseModel):
    earliest_year: int | None = Field(
        description="Expected Close가 가장 이른 Deal의 연도. Deal이 없으면 null."
    )

    @classmethod
    def from_view(cls, view: DealYearsView) -> DealYearsResponse:
        return cls(earliest_year=view.earliest_year)
