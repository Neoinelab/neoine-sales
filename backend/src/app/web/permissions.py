"""역할별 권한 가드(계획 4.10). 로그인(401) 다음에 검사해 미인증이 항상 먼저 거절된다."""

from collections.abc import Callable, Sequence
from typing import Any

from fastapi import APIRouter, Depends

from app.domain.auth.errors import AccessDeniedError
from app.domain.auth.principal import Permission
from app.web.routers.responses import PROBLEM
from app.web.security import SAFE_METHODS, CurrentUser

WRITE_DENIED = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"
ADMIN_DENIED = "관리자 권한이 필요합니다"


async def require_write(user: CurrentUser) -> None:
    if not user.can(Permission.WRITE):
        raise AccessDeniedError(WRITE_DENIED)


async def require_admin(user: CurrentUser) -> None:
    if not user.can(Permission.ADMINISTER):
        raise AccessDeniedError(ADMIN_DENIED)


class BusinessRouter(APIRouter):
    """읽기(GET)는 로그인만, 쓰기(POST/PUT/DELETE)는 WRITE 권한을 요구하는 라우터."""

    def add_api_route(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        methods: set[str] | list[str] | None = None,
        dependencies: Sequence[Any] | None = None,
        responses: dict[int | str, dict[str, Any]] | None = None,
        **kwargs: Any,  # noqa: ANN401 - FastAPI 라우트 옵션을 그대로 전달한다
    ) -> None:
        names = {m.upper() for m in methods or ["GET"]}
        if names - SAFE_METHODS:
            dependencies = [*(dependencies or []), Depends(require_write)]
            responses = {403: PROBLEM, **(responses or {})}
        super().add_api_route(
            path,
            endpoint,
            methods=methods,
            dependencies=dependencies,
            responses=responses,
            **kwargs,
        )


def admin_router(*, prefix: str, tags: list[str]) -> APIRouter:
    """관리자 전용 라우터. 모든 메서드에 ADMINISTER 권한을 요구한다."""
    return APIRouter(
        dependencies=[Depends(require_admin)],
        responses={403: PROBLEM},
        prefix=prefix,
        tags=list(tags),
    )
