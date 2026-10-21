"""Forecast 요약: 로그인한 모든 역할이 읽는다(읽기 전용)."""

from typing import Annotated

from fastapi import Path, Query

from app.domain.common.errors import InvalidValueError
from app.domain.forecast.errors import ForecastSnapshotNotFoundError
from app.domain.forecast.snapshot import YearMonth
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import PROBLEM
from app.web.schemas.forecast import (
    ForecastSearchParams,
    ForecastSnapshotSearchParams,
    ForecastSummaryResponse,
    SnapshotListResponse,
)

router = BusinessRouter(prefix="/api/v1/forecast", tags=["forecast"])


@router.get("/summary", response_model=ForecastSummaryResponse, responses={422: PROBLEM})
async def get_forecast_summary(
    params: Annotated[ForecastSearchParams, Query()], provider: Provider
) -> ForecastSummaryResponse:
    view = await provider.get_forecast_summary().execute(params.to_criteria())
    return ForecastSummaryResponse.from_view(view)


@router.get("/snapshots", response_model=SnapshotListResponse, responses={422: PROBLEM})
async def list_forecast_snapshots(provider: Provider) -> SnapshotListResponse:
    return SnapshotListResponse.from_infos(await provider.list_forecast_snapshots().execute())


@router.get(
    "/snapshots/{period}/summary",
    response_model=ForecastSummaryResponse,
    responses={404: PROBLEM, 422: PROBLEM},
)
async def get_forecast_snapshot_summary(
    period: Annotated[str, Path(description="기준 월 YYYY-MM")],
    params: Annotated[ForecastSnapshotSearchParams, Query()],
    provider: Provider,
) -> ForecastSummaryResponse:
    criteria = params.to_criteria()  # 조건 오류(422)가 기준 월 없음(404)보다 먼저
    try:
        month = YearMonth.parse(period)
    except InvalidValueError:
        raise ForecastSnapshotNotFoundError(period) from None
    view = await provider.get_forecast_snapshot_summary().execute(month, criteria)
    return ForecastSummaryResponse.from_view(view)
