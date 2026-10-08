from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config.profiles import LocalSettings
from app.container import Container
from app.domain.auth.principal import Principal, Role
from app.main import create_app
from tests.fakes.use_cases import FakeUseCases

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from fastapi import FastAPI
    from sqlalchemy.engine import URL

TRUNCATE_ALL = "truncate auth_sessions, deal_actions, deals, customers, partners cascade"
TEST_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
ALLOWED_ORIGIN = "http://localhost:5173"
SESSION_COOKIE = "neoine_session"
LOGIN_COOKIE = "neoine_login"
CSRF_HEADER = {"X-Requested-With": "neoine-web"}
OIDC_SETTINGS: dict[str, object] = {
    "oidc_issuer": "https://adfs.example.com/adfs",
    "oidc_client_id": "neoine-sales",
    "oidc_client_secret": "client-secret-value",
    "oidc_redirect_uri": "http://test/api/v1/auth/callback",
    "oidc_admin_groups": ["Sales-Admins"],
    "oidc_sales_groups": ["Sales-Team"],
}


def make_settings(**overrides: object) -> LocalSettings:
    """실제 환경 파일을 읽지 않는 테스트용 설정."""
    values: dict[str, object] = {
        "database_url": TEST_DATABASE_URL,
        "jwt_secret": "x" * 40,
        "cors_allowed_origins": [ALLOWED_ORIGIN],
    }
    return LocalSettings(_env_file=None, **{**values, **overrides})  # type: ignore[arg-type]


def new_client(
    app: FastAPI, *, token: str | None = None, csrf: bool = True, base_url: str = "http://test"
) -> AsyncClient:
    headers = CSRF_HEADER if csrf else {}
    cookies = {SESSION_COOKIE: token} if token else None
    return AsyncClient(
        transport=ASGITransport(app=app), base_url=base_url, headers=headers, cookies=cookies
    )


@pytest.fixture
def use_cases() -> FakeUseCases:
    return FakeUseCases()


@pytest.fixture
def app(use_cases: FakeUseCases) -> FastAPI:
    return create_app(settings=make_settings(), use_cases=use_cases)


@pytest_asyncio.fixture
async def client(app: FastAPI, use_cases: FakeUseCases) -> AsyncIterator[AsyncClient]:
    """영업 사용자로 로그인한 클라이언트(세션 쿠키 + CSRF 헤더)."""
    token = (await use_cases.dev_login().execute(Role.SALES)).token
    async with new_client(app, token=token) as http:
        yield http


@pytest_asyncio.fixture
async def anonymous_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with new_client(app) as http:
        yield http


def principal_for(subject: str) -> Principal:
    return Principal(subject, f"{subject}@local.test", f"사용자 {subject}", Role.SALES)


@pytest_asyncio.fixture
async def client_for(
    app: FastAPI, use_cases: FakeUseCases
) -> AsyncIterator[Callable[[str], Awaitable[AsyncClient]]]:
    """subject를 주면 그 사용자로 로그인한 클라이언트를 돌려주는 팩토리(Fake UoW)."""
    async with AsyncExitStack() as stack_:

        async def open_client(subject: str) -> AsyncClient:
            token = await use_cases.login_as(principal_for(subject))
            return await stack_.enter_async_context(new_client(app, token=token))

        yield open_client


async def _truncate(database_url: URL) -> None:
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(TRUNCATE_ALL))
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def stack_for(
    test_database_url: URL,
) -> AsyncIterator[Callable[[str], Awaitable[AsyncClient]]]:
    """실제 PostgreSQL을 쓰는 다중 사용자 팩토리. 끝나면 테이블을 비운다."""
    settings = make_settings(database_url=test_database_url.render_as_string(hide_password=False))
    container = Container(settings)
    app = create_app(settings=settings, use_cases=container)
    try:
        async with AsyncExitStack() as stack_:

            async def open_client(subject: str) -> AsyncClient:
                # Container에는 임의 사용자 로그인 공개 API가 없어 세션 발급기를 직접 쓴다
                issued = await container._issue_session.execute(principal_for(subject))
                return await stack_.enter_async_context(new_client(app, token=issued.token))

            yield open_client
    finally:
        await container.dispose()
        await _truncate(test_database_url)


@pytest_asyncio.fixture
async def stack(test_database_url: URL) -> AsyncIterator[AsyncClient]:
    settings = make_settings(database_url=test_database_url.render_as_string(hide_password=False))
    container = Container(settings)
    app = create_app(settings=settings, use_cases=container)
    try:
        token = (await container.dev_login().execute(Role.SALES)).token
        async with new_client(app, token=token) as http:
            yield http
    finally:
        await container.dispose()
        await _truncate(test_database_url)
