"""FastAPI 앱 팩토리. `uvicorn app.main:app`으로 실행한다(첫 접근 때 설정을 읽어 앱을 만든다)."""

import asyncio
from contextlib import asynccontextmanager, suppress
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
    dashboard,
    deal_actions,
    deals,
    forecast,
    health,
    license_contract_attachments,
    license_contracts,
    me,
    partner_meetings,
    reports,
    saved_reports,
    settings_directory,
    settings_storage,
    time,
    user_options,
    users,
    vendors,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.web.use_case_provider import UseCaseProvider
from app.web.routers.responses import PROBLEM
from app.web.security import AuthOptions, require_csrf_header, require_login


def _include_business_routers(app: FastAPI) -> None:
    """로그인(401)과 CSRF 헤더 검사를 거는 라우터를 등록한다."""
    guard = [Depends(require_login), Depends(require_csrf_header)]
    modules = (
        contacts,
        deals,
        deal_actions,
        attachments,
        attachment_items,
        codes,
        bant_labels,
        action_types,
        vendors,
        partner_meetings,
        license_contracts,
        license_contract_attachments,
        forecast,
        dashboard,
        time,
        me,
        user_options,
        reports,
        saved_reports,
        users,
        settings_directory,
        settings_storage,
        alert_settings,
    )
    routers = [module.router for module in modules]
    routers.append(license_contract_attachments.items_router)
    for router in routers:
        app.include_router(router, dependencies=guard, responses={401: PROBLEM})


def create_app(
    settings: Settings | None = None, use_cases: UseCaseProvider | None = None
) -> FastAPI:
    """settings·use_cases를 주입하면 테스트용, 생략하면 실제 설정과 Container를 쓴다."""
    settings = settings or get_settings()
    owned = Container(settings) if use_cases is None else None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        scheduler: asyncio.Task[None] | None = None
        if owned is not None and settings.scheduler_enabled:
            scheduler = asyncio.create_task(owned.forecast_snapshot_scheduler().run_forever())
        try:
            yield
        finally:
            try:
                if scheduler is not None:
                    scheduler.cancel()
                    with suppress(asyncio.CancelledError):
                        await scheduler
            finally:
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
    )
    register_error_handlers(app)
    app.include_router(health.router)
    for module in (auth, auth_login, auth_setup):
        app.include_router(module.router)
    _include_business_routers(app)
    return app


@lru_cache
def _default_app() -> FastAPI:
    return create_app()


def __getattr__(name: str) -> FastAPI:
    if name == "app":
        return _default_app()
    raise AttributeError(name)
