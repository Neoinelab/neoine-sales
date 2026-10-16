"""POST /deals/{code}/changes 요청·응답 스키마. 한 번에 값 하나만 바꾼다."""

from datetime import date
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, Field, StrictInt

from app.application.deal.inputs import DealChangeInput
from app.domain.deal.sync import SyncResolution
from app.web.schemas.common import RequestModel
from app.web.schemas.deal_response import DealDetailResponse

if TYPE_CHECKING:
    from app.application.deal.dto import ApplyChangeResult


class CodeChange(RequestModel):
    field: Literal["status_key", "forecast_key"]
    value: str


class AmountChange(RequestModel):
    field: Literal["revenue_amount"]
    value: StrictInt  # 범위는 도메인 문구가 나가도록 맡긴다


class DateChange(RequestModel):
    field: Literal["revenue_date"]
    value: date


ChangeBody = Annotated[CodeChange | AmountChange | DateChange, Field(discriminator="field")]


class ResolutionRequest(RequestModel):
    """프런트가 사용자에게 물어 얻은 답. 보내지 않은 답은 비워 둔다."""

    revenue_amount: StrictInt | None = None
    revenue_date: date | None = None
    status_key: str | None = None
    forecast_key: str | None = None


class DealChangeRequest(RequestModel):
    change: ChangeBody
    resolution: ResolutionRequest | None = None

    def to_input(self) -> DealChangeInput:
        resolution = (
            SyncResolution(**self.resolution.model_dump()) if self.resolution is not None else None
        )
        return DealChangeInput(
            field=self.change.field, value=self.change.value, resolution=resolution
        )


class CoChangedResponse(BaseModel):
    field: str
    from_: str = Field(serialization_alias="from", validation_alias="from")
    to: str


class DealChangeResponse(BaseModel):
    deal: DealDetailResponse
    co_changed: list[CoChangedResponse]
    notice: str | None

    @classmethod
    def from_result(cls, result: ApplyChangeResult) -> DealChangeResponse:
        return cls(
            deal=DealDetailResponse.from_view(result.view),
            co_changed=[
                CoChangedResponse.model_validate(
                    {"field": str(change.field), "from": change.before, "to": change.after}
                )
                for change in result.co_changed
            ],
            notice=result.notice,
        )
