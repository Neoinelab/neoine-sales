"""최종 업데이트 프리셋 응답(AC-9·11·12): JSON 키는 today, periods[].key/from/to.

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
from tests.functional.conftest import make_settings

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
    async with _client(role=role) as http:
        response = await http.get(URL)

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
    async with _client(role=role) as http:
        response = await http.get(URL)

    assert response.status_code == 200, response.text
    upcoming = response.json()["upcoming"]
    assert [u["key"] for u in upcoming] == ["1m", "2m"]
    assert all(set(u) == {"key", "from", "to"} for u in upcoming)
    assert all(u["from"] == "2026-10-21" for u in upcoming)
    assert [u["to"] for u in upcoming] == ["2026-11-21", "2026-12-21"]


async def test_the_path_is_not_taken_for_a_deal_code() -> None:
    async with _client(role=Role.USER) as http:
        response = await http.get(URL)

    assert response.status_code == 200  # 404(Deal 없음)이 아니다


async def test_without_login_the_presets_are_unauthorized() -> None:
    async with _client(role=None) as http:
        response = await http.get(URL)

    assert response.status_code == 401


async def test_openapi_documents_from_and_to_keys() -> None:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())

    spec = app.openapi()

    assert URL in spec["paths"]
    schemas = spec["components"]["schemas"]
    period = next(
        s
        for name, s in schemas.items()
        if "UpdatedPeriod" in name and "properties" in s and "key" in s["properties"]
    )
    assert {"key", "from", "to"} <= set(period["properties"])


async def test_openapi_documents_upcoming() -> None:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())

    schema = app.openapi()["components"]["schemas"]["UpdatedPeriodsResponse"]

    assert "upcoming" in schema["properties"]
    assert "upcoming" in schema["required"]
