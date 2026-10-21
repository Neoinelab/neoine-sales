"""FastAPI 앱 팩토리. `uvicorn app.main:app`으로 실행한다(첫 접근 때 설정을 읽어 앱을 만든다)."""

from contextlib import asynccontextmanager
from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.container import Container
from app.web.error_handlers import register_error_handlers
from app.web.routers import (
    action_types,
    alert_settings,
    attachment_items,
    attachments,
    auth,
    auth_login,
    auth_setup,
    bant_labels,
    codes,
    contacts,
    deal_actions,
    deals,
    forecast,
    health,
    settings_directory,
    settings_storage,
    user_options,
    users,
    vendors,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.web.use_case_provider import UseCaseProvider
from app.web.routers.responses import PROBLEM
from app.web.security import AuthOptions, require_csrf_header, require_login


def create_app(
    settings: Settings | None = None, use_cases: UseCaseProvider | None = None
) -> FastAPI:
    """settings·use_cases를 주입하면 테스트용, 생략하면 실제 설정과 Container를 쓴다."""
    settings = settings or get_settings()
    owned = Container(settings) if use_cases is None else None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        if owned is not None:
            await owned.dispose()

    app = FastAPI(
        title="neoine-sales API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url="/redoc" if settings.enable_docs else None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )
    app.state.use_cases = use_cases or owned
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.auth_options = AuthOptions(
        cookie_secure=settings.cookie_secure,
        session_ttl_seconds=settings.session_ttl_hours * 3600,
        dev_login_enabled=settings.dev_login_enabled,
    )
    register_error_handlers(app)
    app.include_router(health.router)
    for module in (auth, auth_login, auth_setup):
        app.include_router(module.router)
    guard = [Depends(require_login), Depends(require_csrf_header)]
    business = (
        contacts,
        deals,
        deal_actions,
        attachments,
        attachment_items,
        codes,
        bant_labels,
        action_types,
        vendors,
        forecast,
    )
    for module in (
        *business,
        user_options,
        users,
        settings_directory,
        settings_storage,
        alert_settings,
    ):
        app.include_router(module.router, dependencies=guard, responses={401: PROBLEM})
    return app


@lru_cache
def _default_app() -> FastAPI:
    return create_app()


def __getattr__(name: str) -> FastAPI:
    if name == "app":
        return _default_app()
    raise AttributeError(name)
