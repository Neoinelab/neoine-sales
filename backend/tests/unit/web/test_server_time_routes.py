"""GET /api/v1/time (시간 기준 서버 통일 AC1): FakeUseCases 위의 HTTP 계약.

DB 없이 라우터·스키마·401 매핑을 확인한다. 실제 DB를 지나는 시나리오는 functional(time/)이 맡는다.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories_auth import make_principal
from tests.fakes.unit_of_work import SteppingClock
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import CSRF_HEADER, make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
URL = "/api/v1/time"
MOMENT = datetime(2026, 12, 31, 15, 30, tzinfo=UTC)


@asynccontextmanager
async def _client(
    use_cases: FakeUseCases, *, role: Role | None = None
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    cookies = {}
    if role is not None:
        cookies[SESSION_COOKIE] = await use_cases.login_as(make_principal("root", role))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies=cookies,
    ) as http:
        yield http


async def test_logged_in_user_gets_server_time(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")
    use_cases = FakeUseCases()
    async with _client(use_cases, role=Role.USER) as http:
        use_cases.clock = SteppingClock(MOMENT)  # 로그인 뒤 서버 시계를 고정한다

        response = await http.get(URL)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"now", "today"}
    assert body["now"] == "2027-01-01T00:30:00+09:00"
    assert body["today"] == "2027-01-01"


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_can_read_server_time(role: Role) -> None:
    async with _client(FakeUseCases(), role=role) as http:
        response = await http.get(URL)

    assert response.status_code == 200, response.text


async def test_anonymous_request_is_unauthorized() -> None:
    async with _client(FakeUseCases()) as http:
        response = await http.get(URL)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert str(response.json()["type"]).endswith("unauthenticated")


async def test_openapi_documents_the_time_route_with_a_date_time_now() -> None:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    spec = app.openapi()

    operation = spec["paths"][URL]["get"]
    schema_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    schema = spec["components"]["schemas"][schema_ref.rsplit("/", 1)[1]]
    assert set(schema["properties"]) == {"now", "today"}
    assert set(schema["required"]) == {"now", "today"}
    assert schema["properties"]["now"]["format"] == "date-time"
    assert schema["properties"]["today"]["format"] == "date"
    assert "401" in operation["responses"]
