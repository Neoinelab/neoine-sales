"""local 계정 라우터 단위 테스트 공용 도우미: FakeUseCases 위의 ASGI 클라이언트와 로그인 도우미."""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from httpx import ASGITransport, AsyncClient

from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories_auth import make_principal
from tests.functional.conftest import CSRF_HEADER, make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import Response

    from tests.fakes.use_cases import FakeUseCases

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
PASSWORD = "Passw0rd-ok"  # noqa: S105 - 가짜 값
SETUP = "/api/v1/auth/setup"
SETUP_MODE = "/api/v1/auth/setup/auth-mode"
SETUP_STORAGE = "/api/v1/auth/setup/storage"
LOGIN = "/api/v1/auth/login"
CONFIG = "/api/v1/auth/config"
ME = "/api/v1/auth/me"
USERS = "/api/v1/users"
MY_PROFILE = "/api/v1/me/profile"
MY_PASSWORD = "/api/v1/me/password"  # noqa: S105 - 경로다


def new_client(use_cases: FakeUseCases, cookies: dict[str, str] | None = None) -> AsyncClient:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies=cookies or {},
    )


@asynccontextmanager
async def anonymous(use_cases: FakeUseCases) -> AsyncIterator[AsyncClient]:
    async with new_client(use_cases) as http:
        yield http


@asynccontextmanager
async def signed_in_as(
    use_cases: FakeUseCases, login_id: str, role: Role = Role.SALES
) -> AsyncIterator[AsyncClient]:
    """이미 있는 재직 사용자(없으면 만든다)로 로그인한 클라이언트."""
    token = await use_cases.login_as(make_principal(login_id, role))
    async with new_client(use_cases, {SESSION_COOKIE: token}) as http:
        yield http


async def local_system(use_cases: FakeUseCases) -> None:
    """local 모드로 1~2단계를 마친 시스템(admin은 아직 없다)."""
    await use_cases.seed_auth_mode(AuthMode.LOCAL)
    await use_cases.seed_storage()


def problem(response: Response, status: int, kind: str) -> dict[str, object]:
    assert response.status_code == status, response.text
    body = response.json()
    assert str(body["type"]).endswith(kind), body
    return dict(body)


def error_locations(body: dict[str, object]) -> list[list[object]]:
    errors = body["errors"]
    assert isinstance(errors, list)
    return [list(e["location"]) for e in errors]
