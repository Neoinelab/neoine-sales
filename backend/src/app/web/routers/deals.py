from uuid import UUID

from fastapi import APIRouter, Response, status

from app.domain.deal.value_objects import DealId
from app.web.dependencies import DEFAULT_LIMIT, Limit, Offset, Provider
from app.web.routers.responses import READ_ERRORS, WRITE_ERRORS
from app.web.schemas.deal import DealPage, DealRequest, DealResponse

router = APIRouter(prefix="/api/v1/deals", tags=["deals"])


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=DealResponse, responses=WRITE_ERRORS
)
async def register_deal(body: DealRequest, response: Response, provider: Provider) -> DealResponse:
    deal = await provider.register_deal().execute(body.to_input())
    response.headers["Location"] = f"{router.prefix}/{deal.id}"
    return DealResponse.from_entity(deal)


@router.get("", response_model=DealPage, responses=READ_ERRORS)
async def list_deals(
    provider: Provider, offset: Offset = 0, limit: Limit = DEFAULT_LIMIT
) -> DealPage:
    deals = await provider.list_deals().execute(offset=offset, limit=limit)
    return DealPage(items=[DealResponse.from_entity(d) for d in deals], offset=offset, limit=limit)


# 고정 경로(by-code)를 /{deal_id}보다 먼저 선언해야 UUID로 해석되지 않는다
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
