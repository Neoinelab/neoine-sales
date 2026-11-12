"""GET /api/v1/time (시간 기준 서버 통일 AC1): FakeUseCases 위의 HTTP 계약.

DB 없이 라우터·스키마·401 매핑을 확인한다.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories_auth import make_principal
from tests.fakes.unit_of_work import FixedClock
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import CSRF_HEADER, make_settings

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
    """로그인한 사용자는 서버 업무 시각(+09:00)과 업무 날짜를 받는다.

    테스트 코드: TM-001
    """
    # given: 서버 시간대 Asia/Seoul, 서버 시계 2026-12-31T15:30Z, user로 로그인
    local_tz("Asia/Seoul")
    use_cases = FakeUseCases()
    async with _client(use_cases, role=Role.USER) as http:
        use_cases.clock = FixedClock(MOMENT)  # 로그인 뒤 서버 시계를 고정한다
        # when: GET /api/v1/time
        response = await http.get(URL)

    # then: 키는 now·today뿐이고 now는 서버 시계와 같은 순간의 서울 시각, today는 다음 날이다
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"now", "today"}
    assert body["now"] == "2027-01-01T00:30:00+09:00"
    assert datetime.fromisoformat(body["now"]) == MOMENT
    assert body["today"] == "2027-01-01"


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_can_read_server_time(role: Role) -> None:
    """세 역할 모두 서버 시각을 읽을 수 있다.

    테스트 코드: TM-002
    """
    # given: 역할별로 로그인
    async with _client(FakeUseCases(), role=role) as http:
        # when: GET /api/v1/time
        response = await http.get(URL)

    # then: 모두 200
    assert response.status_code == 200, response.text


async def test_anonymous_request_is_unauthorized() -> None:
    """로그인하지 않으면 서버 시각은 401이다.

    테스트 코드: TM-003
    """
    # given: 로그인하지 않은 클라이언트
    async with _client(FakeUseCases()) as http:
        # when: GET /api/v1/time
        response = await http.get(URL)

    # then: 401 problem+json, type이 unauthenticated로 끝난다
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert str(response.json()["type"]).endswith("unauthenticated")


async def test_today_is_next_day_when_utc_is_still_previous_day(
    local_tz: Callable[[str], None],
) -> None:
    """UTC로는 전날이어도 업무 날짜는 서버 시간대의 다음 날이다.

    테스트 코드: TM-004
    """
    # given: 서버 시간대 Asia/Seoul, 서버 시계 2026-10-22T15:00Z, sales로 로그인
    local_tz("Asia/Seoul")
    use_cases = FakeUseCases()
    async with _client(use_cases, role=Role.SALES) as http:
        use_cases.clock = FixedClock(datetime(2026, 10, 22, 15, 0, tzinfo=UTC))
        # when: GET /api/v1/time
        response = await http.get(URL)

    # then: today는 2026-10-23이고 now의 날짜 부분과 같다
    body = response.json()
    assert response.status_code == 200, response.text
    assert body["today"] == "2026-10-23"
    assert body["now"][:10] == body["today"]


async def test_openapi_documents_the_time_route_with_a_date_time_now() -> None:
    """openapi에 서버 시각 응답 모양과 401이 문서화된다.

    테스트 코드: TM-007
    """
    # given: 앱
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    # when: openapi 문서를 만든다
    spec = app.openapi()

    # then: now는 date-time, today는 date, 둘 다 required이고 401이 있다
    operation = spec["paths"][URL]["get"]
    schema_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    schema = spec["components"]["schemas"][schema_ref.rsplit("/", 1)[1]]
    assert set(schema["properties"]) == {"now", "today"}
    assert set(schema["required"]) == {"now", "today"}
    assert schema["properties"]["now"]["format"] == "date-time"
    assert schema["properties"]["today"]["format"] == "date"
    assert "401" in operation["responses"]
