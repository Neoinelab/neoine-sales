"""사용자 선택 UI용 후보 목록. 로그인한 모든 역할이 읽고, 이메일·역할은 내려주지 않는다."""

from typing import Annotated

from fastapi import Query
from pydantic import Field

from app.application.ports.deal_repository import KEYWORD_MAX
from app.application.ports.pagination import MAX_LIMIT
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import READ_ERRORS
from app.web.schemas.common import RequestModel
from app.web.schemas.user import UserOptionPage
from app.web.schemas.user_ref import UserRef

router = BusinessRouter(prefix="/api/v1/user-options", tags=["users"])


class UserOptionParams(RequestModel):
    """모르는 쿼리 파라미터는 422. 기본은 재직자만, include_resigned=true는 검색 필터용이다."""

    include_resigned: bool = False
    keyword: Annotated[str | None, Field(max_length=KEYWORD_MAX)] = None
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = MAX_LIMIT


@router.get("", response_model=UserOptionPage, responses={422: READ_ERRORS[422]})
async def list_user_options(
    params: Annotated[UserOptionParams, Query()], provider: Provider
) -> UserOptionPage:
    refs = await provider.list_user_options().execute(
        keyword=params.keyword, include_resigned=params.include_resigned, limit=params.limit
    )
    return UserOptionPage(
        items=[UserRef.from_domain(r) for r in refs], offset=0, limit=params.limit
    )
