from typing import Annotated

from fastapi import Query, Response, status

from app.application.deal.inputs import Actor
from app.domain.deal.history import HistoryCategory
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import PROBLEM, READ_ERRORS, WRITE_ERRORS
from app.web.schemas.deal import (
    DealChangeRequest,
    DealCreateRequest,
    DealPatchRequest,
    DealSearchParams,
)
from app.web.schemas.deal_change import DealChangeResponse
from app.web.schemas.deal_response import (
    DealDetailResponse,
    DealRowPage,
    DeletionImpactResponse,
    HistoryEntryResponse,
    row_page,
)
from app.web.schemas.deal_years import DealYearsResponse
from app.web.schemas.updated_period import UpdatedPeriodsResponse
from app.web.security import CurrentUser

router = BusinessRouter(prefix="/api/v1/deals", tags=["deals"])


def _actor(user: CurrentUser) -> Actor:
    return Actor(user_id=user.user_id, role=user.role)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=DealDetailResponse,
    responses=WRITE_ERRORS,
)
async def register_deal(
    body: DealCreateRequest, response: Response, user: CurrentUser, provider: Provider
) -> DealDetailResponse:
    view = await provider.register_deal().execute(body.to_input(), _actor(user))
    response.headers["Location"] = f"{router.prefix}/{view.item.deal.id.value}"
    return DealDetailResponse.from_view(view)


@router.get("", response_model=DealRowPage, responses={422: PROBLEM})
async def list_deals(
    params: Annotated[DealSearchParams, Query()], user: CurrentUser, provider: Provider
) -> DealRowPage:
    return row_page(await provider.list_deals().execute(params.to_query(user.user_id)))


@router.get("/updated-periods", response_model=UpdatedPeriodsResponse)
async def list_updated_periods(provider: Provider) -> UpdatedPeriodsResponse:
    return UpdatedPeriodsResponse.from_view(await provider.list_updated_periods().execute())


@router.get("/years", response_model=DealYearsResponse)
async def get_deal_years(provider: Provider) -> DealYearsResponse:
    return DealYearsResponse.from_view(await provider.get_deal_years().execute())


@router.get("/{code}", response_model=DealDetailResponse, responses=READ_ERRORS)
async def get_deal(code: str, provider: Provider) -> DealDetailResponse:
    return DealDetailResponse.from_view(await provider.get_deal().execute(code))


@router.patch("/{code}", response_model=DealDetailResponse, responses=WRITE_ERRORS)
async def update_deal(
    code: str, body: DealPatchRequest, user: CurrentUser, provider: Provider
) -> DealDetailResponse:
    view = await provider.update_deal().execute(code, body.to_input(), _actor(user))
    return DealDetailResponse.from_view(view)


@router.delete(
    "/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: PROBLEM, 422: PROBLEM},
)
async def delete_deal(
    code: str, confirm_code: Annotated[str, Query()], user: CurrentUser, provider: Provider
) -> None:
    await provider.delete_deal().execute(code, confirm_code, _actor(user))


@router.get("/{code}/history", response_model=list[HistoryEntryResponse], responses=READ_ERRORS)
async def list_deal_history(
    code: str, provider: Provider, category: Annotated[HistoryCategory | None, Query()] = None
) -> list[HistoryEntryResponse]:
    views = await provider.list_deal_history().execute(code, category)
    return [HistoryEntryResponse.from_view(view) for view in views]


@router.get("/{code}/deletion-impact", response_model=DeletionImpactResponse, responses=READ_ERRORS)
async def get_deal_deletion_impact(code: str, provider: Provider) -> DeletionImpactResponse:
    impact = await provider.get_deal_deletion_impact().execute(code)
    return DeletionImpactResponse(
        history_count=impact.history_count,
        action_count=impact.action_count,
        attachment_count=impact.attachment_count,
        partner_meeting_count=impact.partner_meeting_count,
    )


@router.post("/{code}/changes", response_model=DealChangeResponse, responses=WRITE_ERRORS)
async def apply_deal_change(
    code: str, body: DealChangeRequest, user: CurrentUser, provider: Provider
) -> DealChangeResponse:
    result = await provider.apply_deal_change().execute(code, body.to_input(), _actor(user))
    return DealChangeResponse.from_result(result)
