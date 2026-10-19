"""Vendor 라우터 단위 테스트 공용 도우미: FakeUseCases 위의 ASGI 클라이언트와 Problem 단언."""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from httpx import ASGITransport, AsyncClient

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
URL = "/api/v1/vendors"
VENDOR_KEYS = {"id", "name", "usage_count", "solutions", "created_at", "updated_at"}
SOLUTION_KEYS = {"id", "vendor_id", "name", "usage_count", "created_at", "updated_at"}


@asynccontextmanager
async def client_for(
    use_cases: FakeUseCases, *, role: Role | None = Role.ADMIN
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    cookies = {}
    if role is not None:
        cookies[SESSION_COOKIE] = await use_cases.login_as(
            make_principal("root" if role is Role.ADMIN else f"{role.value}-user", role)
        )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies=cookies,
    ) as http:
        yield http


def problem(response: Response, status: int, kind: str) -> dict[str, object]:
    assert response.status_code == status, response.text
    body = response.json()
    assert str(body["type"]).endswith(kind), body
    return dict(body)


async def make_vendor(http: AsyncClient, name: str = "SAP") -> dict[str, object]:
    response = await http.post(URL, json={"name": name})
    assert response.status_code == 201, response.text
    return dict(response.json())


async def make_solution(http: AsyncClient, vendor_id: object, name: str) -> dict[str, object]:
    response = await http.post(f"{URL}/{vendor_id}/solutions", json={"name": name})
    assert response.status_code == 201, response.text
    return dict(response.json())
