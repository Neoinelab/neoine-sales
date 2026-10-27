"""Reports: 필드 카탈로그와 임시 조회. 조회 전용(저장 없음)이라 POST여도 쓰기 권한이 필요 없다."""

from fastapi import APIRouter

from app.web.dependencies import Provider
from app.web.routers.responses import PROBLEM
from app.web.schemas.report_fields import ReportCatalogResponse
from app.web.schemas.report_query import ReportQueryRequest, ReportQueryResponse

# BusinessRouter가 아니다: POST /query도 모든 로그인 역할이 호출한다(저장·변경 없음).
router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/fields", response_model=ReportCatalogResponse)
async def list_report_fields(provider: Provider) -> ReportCatalogResponse:
    return ReportCatalogResponse.from_view(provider.list_report_fields().execute())


@router.post(
    "/query",
    response_model=ReportQueryResponse,
    responses={422: PROBLEM, 503: PROBLEM},
)
async def run_report(body: ReportQueryRequest, provider: Provider) -> ReportQueryResponse:
    view = await provider.run_report().execute(body.to_raw())
    return ReportQueryResponse.from_view(view)
