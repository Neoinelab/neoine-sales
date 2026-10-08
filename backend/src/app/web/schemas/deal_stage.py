from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.application.deal.inputs import StageChangeInput
from app.application.ports.deal_stage_change_repository import DealStageChangeQuery
from app.application.ports.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.domain.auth.principal import Principal
from app.domain.deal.pipeline import CurrencyAmount, DealPipeline, StageSummary
from app.domain.deal.stage import DealStage, DealStageChange
from app.domain.deal.value_objects import DealId
from app.web.schemas.common import Page, RequestModel


class DealStageChangeRequest(RequestModel):
    stage: DealStage
    reason: str | None = None

    def to_input(self, user: Principal) -> StageChangeInput:
        return StageChangeInput(
            stage=self.stage,
            reason=self.reason,
            changed_by_subject=user.subject,
            changed_by_name=user.name,
        )


class DealStageChangeResponse(BaseModel):
    id: str
    deal_id: str
    from_stage: DealStage
    to_stage: DealStage
    reason: str | None
    changed_by_subject: str
    changed_by_name: str
    changed_at: datetime

    @classmethod
    def from_entity(cls, change: DealStageChange) -> DealStageChangeResponse:
        return cls(
            id=str(change.id),
            deal_id=str(change.deal_id),
            from_stage=change.from_stage,
            to_stage=change.to_stage,
            reason=change.reason,
            changed_by_subject=change.changed_by.subject,
            changed_by_name=change.changed_by.name,
            changed_at=change.changed_at,
        )


class DealStageChangeSearchParams(RequestModel):
    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT

    def to_query(self, deal_id: UUID) -> DealStageChangeQuery:
        return DealStageChangeQuery(deal_id=DealId(deal_id), offset=self.offset, limit=self.limit)


DealStageChangePage = Page[DealStageChangeResponse]


class PipelineParams(RequestModel):
    """파이프라인 조회 쿼리. mine=true면 내가 등록한 딜만 집계한다. 모르는 파라미터는 422."""

    mine: bool = False


class CurrencyAmountResponse(BaseModel):
    currency: str
    amount: str  # 문자열: 소수 정밀도 보존

    @classmethod
    def from_value(cls, total: CurrencyAmount) -> CurrencyAmountResponse:
        return cls(currency=total.currency, amount=format(total.amount.normalize(), "f"))


class StageSummaryResponse(BaseModel):
    stage: DealStage
    deal_count: int
    totals: list[CurrencyAmountResponse]

    @classmethod
    def from_value(cls, summary: StageSummary) -> StageSummaryResponse:
        return cls(
            stage=summary.stage,
            deal_count=summary.deal_count,
            totals=[CurrencyAmountResponse.from_value(t) for t in summary.totals],
        )


class DealPipelineResponse(BaseModel):
    stages: list[StageSummaryResponse]

    @classmethod
    def from_value(cls, pipeline: DealPipeline) -> DealPipelineResponse:
        return cls(stages=[StageSummaryResponse.from_value(s) for s in pipeline.stages])
