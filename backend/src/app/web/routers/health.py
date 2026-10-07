import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.web.dependencies import Provider
from app.web.error_handlers import problem

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/healthz")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=None)
async def readiness(request: Request, provider: Provider) -> JSONResponse | dict[str, str]:
    try:
        await provider.check_ready()
    except Exception:
        logger.exception("readiness check failed")  # 원인은 로그에만 남기고 응답에는 싣지 않는다
        return problem(request, 503, "not-ready", "서비스가 아직 요청을 받을 수 없습니다")
    return {"status": "ready"}
