"""최종 업데이트 프리셋 응답: JSON 키는 today, periods[].key/from/to.

라우트는 /{code}보다 먼저 등록되어야 한다.
"""

from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories import NOW
from tests.factories_auth import make_principal
from tests.fakes.unit_of_work import FixedClock
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
URL = "/api/v1/deals/updated-periods"


@asynccontextmanager
async def _client(*, role: Role | None) -> AsyncIterator[AsyncClient]:
    use_cases = FakeUseCases()
    clock = use_cases.clock
    assert isinstance(clock, FixedClock)
    clock.advance((datetime(2026, 10, 21, 12, 0).astimezone() - NOW).total_seconds())
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    cookies = {}
    if role is not None:
        cookies[SESSION_COOKIE] = await use_cases.login_as(make_principal("root", role))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as http:
        yield http


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_gets_the_five_presets_with_from_and_to_keys(role: Role) -> None:
    """모든 역할이 from·to 키를 가진 다섯 프리셋을 받는다."""
    # when: 역할별로 프리셋을 조회한다
    async with _client(role=role) as http:
        response = await http.get(URL)

    # then: 200이고 오늘·프리셋 다섯 개의 키와 날짜 범위가 기대와 같다
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"today", "periods", "upcoming"}
    assert body["today"] == "2026-10-21"
    assert [p["key"] for p in body["periods"]] == ["2w", "1m", "2m", "3m", "6m"]
    assert all(set(p) == {"key", "from", "to"} for p in body["periods"])
    assert all(p["to"] == "2026-10-21" for p in body["periods"])
    assert body["periods"][0]["from"] == "2026-10-07"
    assert body["periods"][4]["from"] == "2026-04-21"
    assert all(date.fromisoformat(p["from"]) for p in body["periods"])


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_gets_the_upcoming_presets(role: Role) -> None:
    """모든 역할이 다가오는 기간 프리셋을 받는다."""
    # when: 역할별로 프리셋을 조회한다
    async with _client(role=role) as http:
        response = await http.get(URL)

    # then: 200이고 1m·2m 프리셋이 오늘부터 시작한다
    assert response.status_code == 200, response.text
    upcoming = response.json()["upcoming"]
    assert [u["key"] for u in upcoming] == ["1m", "2m"]
    assert all(set(u) == {"key", "from", "to"} for u in upcoming)
    assert all(u["from"] == "2026-10-21" for u in upcoming)
    assert [u["to"] for u in upcoming] == ["2026-11-21", "2026-12-21"]


async def test_the_path_is_not_taken_for_a_deal_code() -> None:
    """경로가 Deal 코드로 해석되지 않는다."""
    # when: USER 역할로 프리셋 경로를 조회한다
    async with _client(role=Role.USER) as http:
        response = await http.get(URL)

    # then: 200이다
    assert response.status_code == 200  # 404(Deal 없음)이 아니다


async def test_without_login_the_presets_are_unauthorized() -> None:
    """로그인하지 않으면 프리셋 조회는 401이다."""
    # when: 로그인 없이 조회한다
    async with _client(role=None) as http:
        response = await http.get(URL)

    # then: 401이다
    assert response.status_code == 401


async def test_openapi_documents_from_and_to_keys() -> None:
    """OpenAPI 문서에 key·from·to 필드가 기술되어 있다."""
    # given: 앱
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())

    # when: OpenAPI 문서를 만든다
    spec = app.openapi()

    # then: 경로가 있고 기간 스키마에 key·from·to가 있다
    assert URL in spec["paths"]
    schemas = spec["components"]["schemas"]
    period = next(
        s
        for name, s in schemas.items()
        if "UpdatedPeriod" in name and "properties" in s and "key" in s["properties"]
    )
    assert {"key", "from", "to"} <= set(period["properties"])


async def test_openapi_documents_upcoming() -> None:
    """OpenAPI 문서의 응답 스키마에 upcoming이 필수로 있다."""
    # given: 앱
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())

    # when: 응답 스키마를 읽는다
    schema = app.openapi()["components"]["schemas"]["UpdatedPeriodsResponse"]

    # then: upcoming이 속성이자 필수 필드다
    assert "upcoming" in schema["properties"]
    assert "upcoming" in schema["required"]
