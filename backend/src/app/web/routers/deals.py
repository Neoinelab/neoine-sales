from typing import Annotated
from uuid import UUID

from fastapi import Query, Response, status

from app.domain.deal.value_objects import DealId
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import READ_ERRORS, WRITE_ERRORS
from app.web.schemas.deal import DealPage, DealRequest, DealResponse, DealSearchParams
from app.web.schemas.deal_stage import DealPipelineResponse, PipelineParams
from app.web.security import CurrentUser

router = BusinessRouter(prefix="/api/v1/deals", tags=["deals"])


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=DealResponse, responses=WRITE_ERRORS
)
async def register_deal(
    body: DealRequest, response: Response, user: CurrentUser, provider: Provider
) -> DealResponse:
    deal = await provider.register_deal().execute(body.to_input(), owner_user_id=user.subject)
    response.headers["Location"] = f"{router.prefix}/{deal.id}"
    return DealResponse.from_entity(deal)


@router.get("", response_model=DealPage, responses=READ_ERRORS)
async def list_deals(
    params: Annotated[DealSearchParams, Query()], user: CurrentUser, provider: Provider
) -> DealPage:
    query = params.to_query(user.subject)
    deals = await provider.list_deals().execute(query)
    return DealPage(
        items=[DealResponse.from_entity(d) for d in deals], offset=query.offset, limit=query.limit
    )


# 고정 경로(pipeline, by-code)를 /{deal_id}보다 먼저 선언해야 UUID로 해석되지 않는다
@router.get("/pipeline", response_model=DealPipelineResponse, responses=READ_ERRORS)
async def get_deal_pipeline(
    params: Annotated[PipelineParams, Query()], user: CurrentUser, provider: Provider
) -> DealPipelineResponse:
    owner = user.subject if params.mine else None
    return DealPipelineResponse.from_value(
        await provider.get_deal_pipeline().execute(owner_user_id=owner)
    )


@router.get("/by-code/{code}", response_model=DealResponse, responses=READ_ERRORS)
async def get_deal_by_code(code: str, provider: Provider) -> DealResponse:
    return DealResponse.from_entity(await provider.get_deal_by_code().execute(code))


@router.get("/{deal_id}", response_model=DealResponse, responses=READ_ERRORS)
async def get_deal(deal_id: UUID, provider: Provider) -> DealResponse:
    return DealResponse.from_entity(await provider.get_deal().execute(DealId(deal_id)))


@router.put("/{deal_id}", response_model=DealResponse, responses=WRITE_ERRORS)
async def update_deal(deal_id: UUID, body: DealRequest, provider: Provider) -> DealResponse:
    deal = await provider.update_deal().execute(DealId(deal_id), body.to_input())
    return DealResponse.from_entity(deal)


@router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT, responses=READ_ERRORS)
async def delete_deal(deal_id: UUID, provider: Provider) -> None:
    await provider.delete_deal().execute(DealId(deal_id))
