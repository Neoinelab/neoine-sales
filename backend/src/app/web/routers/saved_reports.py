"""저장 리포트: 목록·만들기·열기·수정·삭제·복제·실행. 로그인한 모든 역할이 쓴다(user 포함).

공개 범위·소유자 판정은 도메인이 한다. `reports.py`(`/fields`·`/query`)보다 뒤에 등록해야
`GET /fields`가 `/{report_id}`에 걸리지 않는다.
"""

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Response, status

from app.application.report.saved_inputs import ReportViewer
from app.domain.saved_report.values import ReportId
from app.web.dependencies import Provider
from app.web.routers.responses import PROBLEM
from app.web.schemas.ids import PathId
from app.web.schemas.report_query import ReportQueryResponse
from app.web.schemas.saved_report import (
    ReportCopyRequest,
    ReportCreateRequest,
    ReportDetailResponse,
    ReportLayoutUpdateRequest,
    ReportSummaryResponse,
    ReportUpdateRequest,
    report_user_ids,
    summaries,
)
from app.web.schemas.user_ref import resolve_refs
from app.web.security import CurrentUser

if TYPE_CHECKING:
    from app.domain.saved_report.entities import Report

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])
CREATED = status.HTTP_201_CREATED
NO_CONTENT = status.HTTP_204_NO_CONTENT
NOT_FOUND: dict[int | str, dict[str, Any]] = {404: PROBLEM, 422: PROBLEM}
SAVE_ERRORS: dict[int | str, dict[str, Any]] = {409: PROBLEM, 422: PROBLEM}


def _viewer(user: CurrentUser) -> ReportViewer:
    return ReportViewer(user_id=user.user_id, role=user.role)


async def _detail(provider: Provider, report: Report) -> ReportDetailResponse:
    refs = await resolve_refs(provider, report_user_ids([report]))
    return ReportDetailResponse.from_detail(report, refs)


@router.get("", response_model=list[ReportSummaryResponse])
async def list_reports(user: CurrentUser, provider: Provider) -> list[ReportSummaryResponse]:
    items = list(await provider.list_reports().execute(_viewer(user)))
    refs = await resolve_refs(provider, report_user_ids([i.report for i in items]))
    return summaries(items, refs)


@router.post("", status_code=CREATED, response_model=ReportDetailResponse, responses=SAVE_ERRORS)
async def create_report(
    body: ReportCreateRequest, response: Response, user: CurrentUser, provider: Provider
) -> ReportDetailResponse:
    report = await provider.create_report().execute(body.to_input(), _viewer(user))
    response.headers["Location"] = f"{router.prefix}/{report.id}"
    return await _detail(provider, report)


@router.get("/{report_id}", response_model=ReportDetailResponse, responses=NOT_FOUND)
async def get_report(
    report_id: PathId, user: CurrentUser, provider: Provider
) -> ReportDetailResponse:
    report = await provider.get_report().execute(ReportId(report_id), _viewer(user))
    return await _detail(provider, report)


@router.put(
    "/{report_id}",
    response_model=ReportDetailResponse,
    responses={403: PROBLEM, 404: PROBLEM, **SAVE_ERRORS},
)
async def update_report(
    report_id: PathId, body: ReportUpdateRequest, user: CurrentUser, provider: Provider
) -> ReportDetailResponse:
    report = await provider.update_report().execute(
        ReportId(report_id), body.to_input(), body.revision, _viewer(user)
    )
    return await _detail(provider, report)


@router.put(
    "/{report_id}/layout",
    response_model=ReportDetailResponse,
    responses={403: PROBLEM, 404: PROBLEM, **SAVE_ERRORS},
)
async def change_report_layout(
    report_id: PathId, body: ReportLayoutUpdateRequest, user: CurrentUser, provider: Provider
) -> ReportDetailResponse:
    report = await provider.change_report_layout().execute(
        ReportId(report_id), body.layout.to_raw(), body.revision, _viewer(user)
    )
    return await _detail(provider, report)


@router.delete("/{report_id}", status_code=NO_CONTENT, responses={403: PROBLEM, **NOT_FOUND})
async def delete_report(report_id: PathId, user: CurrentUser, provider: Provider) -> None:
    await provider.delete_report().execute(ReportId(report_id), _viewer(user))


@router.post(
    "/{report_id}/copy",
    status_code=CREATED,
    response_model=ReportDetailResponse,
    responses={404: PROBLEM, **SAVE_ERRORS},
)
async def copy_report(
    report_id: PathId,
    body: ReportCopyRequest,
    response: Response,
    user: CurrentUser,
    provider: Provider,
) -> ReportDetailResponse:
    report = await provider.copy_report().execute(
        ReportId(report_id), body.to_meta(), _viewer(user)
    )
    response.headers["Location"] = f"{router.prefix}/{report.id}"
    return await _detail(provider, report)


@router.post(
    "/{report_id}/run",
    response_model=ReportQueryResponse,
    responses={404: PROBLEM, 422: PROBLEM, 503: PROBLEM},
)
async def run_saved_report(
    report_id: PathId, user: CurrentUser, provider: Provider
) -> ReportQueryResponse:
    view = await provider.run_saved_report().execute(ReportId(report_id), _viewer(user))
    return ReportQueryResponse.from_view(view)
