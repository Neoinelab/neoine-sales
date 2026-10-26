"""서버 시각 조회: 로그인한 모든 역할이 읽는다."""

from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.schemas.time import ServerTimeResponse

router = BusinessRouter(prefix="/api/v1/time", tags=["time"])


@router.get("", response_model=ServerTimeResponse)
async def get_server_time(provider: Provider) -> ServerTimeResponse:
    view = await provider.get_server_time().execute()
    return ServerTimeResponse.from_view(view)
