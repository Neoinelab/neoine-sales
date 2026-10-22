"""Dashboard 요약: 로그인한 모든 역할이 읽는다(읽기 전용)."""

from typing import Annotated

from fastapi import Query

from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import PROBLEM
from app.web.schemas.dashboard import DashboardSearchParams, DashboardSummaryResponse

router = BusinessRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse, responses={422: PROBLEM})
async def get_dashboard_summary(
    params: Annotated[DashboardSearchParams, Query()], provider: Provider
) -> DashboardSummaryResponse:
    view = await provider.get_dashboard_summary().execute(params.to_criteria())
    return DashboardSummaryResponse.from_view(view)
