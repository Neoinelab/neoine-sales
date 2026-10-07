from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config.profiles import LocalSettings
from app.domain.auth.principal import Role
from app.main import create_app
from tests.fakes.use_cases import FakeUseCases

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI

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
