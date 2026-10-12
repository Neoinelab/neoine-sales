"""Deal 단계 변경과 변경 이력. 단계는 PUT이 아니라 전용 동작으로만 바꾼다."""

from typing import Annotated
from uuid import UUID

from fastapi import Query

from app.domain.deal.value_objects import DealId
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import READ_ERRORS, WRITE_ERRORS
from app.web.schemas.deal import DealResponse
from app.web.schemas.deal_stage import (
    DealStageChangePage,
    DealStageChangeRequest,
    DealStageChangeResponse,
    DealStageChangeSearchParams,
)
from app.web.security import CurrentUser

router = BusinessRouter(prefix="/api/v1/deals", tags=["deals"])


@router.post("/{deal_id}/stage", response_model=DealResponse, responses=WRITE_ERRORS)
async def change_deal_stage(
    deal_id: UUID, body: DealStageChangeRequest, user: CurrentUser, provider: Provider
) -> DealResponse:
    deal = await provider.change_deal_stage().execute(DealId(deal_id), body.to_input(user))
    return DealResponse.from_entity(deal)


@router.get("/{deal_id}/stage-changes", response_model=DealStageChangePage, responses=READ_ERRORS)
async def list_deal_stage_changes(
    deal_id: UUID, params: Annotated[DealStageChangeSearchParams, Query()], provider: Provider
) -> DealStageChangePage:
    query = params.to_query(deal_id)
    changes = await provider.list_deal_stage_changes().execute(query)
    return DealStageChangePage(
        items=[DealStageChangeResponse.from_entity(c) for c in changes],
        offset=query.offset,
        limit=query.limit,
    )
