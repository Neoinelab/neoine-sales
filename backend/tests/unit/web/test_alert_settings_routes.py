"""경고 기준 라우터(P3 AC-05~07): FakeUseCases 위의 HTTP 계약과 판정 순서(401, csrf, 403, 422).

DB 없이 라우터·스키마·오류 매핑·권한을 빠르게 확인하는 단위 테스트다. 실제 DB를 지나는 시나리오는
functional(settings/test_alert_settings.py)이 맡는다.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.main import create_app
from app.web.permissions import ADMIN_DENIED
from tests.factories_auth import make_principal
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import CSRF_HEADER, make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import Response

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
URL = "/api/v1/alert-settings"
RANGE_MESSAGE = "미업데이트 기준은 1~365일 사이의 정수로 입력하세요."
RESPONSE_KEYS = {"stale_days", "updated_at", "updated_by"}


@asynccontextmanager
async def _client(
    use_cases: FakeUseCases, *, role: Role | None = None, csrf: bool = True
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    cookies = {}
    if role is not None:
        cookies[SESSION_COOKIE] = await use_cases.login_as(make_principal("root", role))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER if csrf else {},
        cookies=cookies,
    ) as http:
        yield http


def _problem(response: Response, status: int, kind: str) -> dict[str, object]:
    assert response.status_code == status, response.text
    body = response.json()
    assert str(body["type"]).endswith(kind), body
    return dict(body)


# ---- GET ----


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_get_is_open_to_every_role_and_defaults_to_fourteen_days(role: Role) -> None:
    async with _client(FakeUseCases(), role=role) as http:
        response = await http.get(URL)

    assert response.status_code == 200, response.text
    assert response.json() == {"stale_days": 14, "updated_at": None, "updated_by": None}


async def test_get_after_an_admin_saved_shows_the_value_the_time_and_the_saver() -> None:
    use_cases = FakeUseCases()
    async with _client(use_cases, role=Role.ADMIN) as http:
        await http.put(URL, json={"stale_days": 30})
        body = (await http.get(URL)).json()
        me = (await http.get("/api/v1/auth/me")).json()

    assert set(body) == RESPONSE_KEYS
    assert body["stale_days"] == 30
    assert body["updated_at"] is not None
    assert body["updated_by"]["id"] == me["user_id"]
    assert set(body["updated_by"]) == {"id", "name", "resigned", "label", "role"}


# ---- PUT ----


async def test_put_by_admin_returns_the_saved_result() -> None:
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        response = await http.put(URL, json={"stale_days": 7})

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == RESPONSE_KEYS
    assert body["stale_days"] == 7
    assert body["updated_by"]["resigned"] is False


@pytest.mark.parametrize("days", [1, 365])
async def test_put_accepts_the_bounds(days: int) -> None:
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        response = await http.put(URL, json={"stale_days": days})

    assert response.status_code == 200, response.text
    assert response.json()["stale_days"] == days


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_put_by_sales_or_user_is_forbidden_and_saves_nothing(role: Role) -> None:
    use_cases = FakeUseCases()
    async with _client(use_cases, role=role) as http:
        response = await http.put(URL, json={"stale_days": 7})
        current = await http.get(URL)

    assert _problem(response, 403, "forbidden")["detail"] == ADMIN_DENIED
    assert current.json()["stale_days"] == 14


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_put_by_a_non_admin_with_a_bad_body_is_still_403(role: Role) -> None:
    async with _client(FakeUseCases(), role=role) as http:
        response = await http.put(URL, json={"garbage": 1})

    _problem(response, 403, "forbidden")


@pytest.mark.parametrize("days", [0, 366, -1])
async def test_put_out_of_range_is_invalid_value_and_keeps_the_stored_value(days: int) -> None:
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        await http.put(URL, json={"stale_days": 21})
        response = await http.put(URL, json={"stale_days": days})
        current = await http.get(URL)

    assert _problem(response, 422, "invalid-value")["detail"] == RANGE_MESSAGE
    assert current.json()["stale_days"] == 21


@pytest.mark.parametrize("value", ["7", 7.5, True, None, [7]])
async def test_put_string_or_float_or_bool_is_request_validation(value: object) -> None:
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        response = await http.put(URL, json={"stale_days": value})
        current = await http.get(URL)

    _problem(response, 422, "request-validation")
    assert current.json()["stale_days"] == 14


async def test_put_with_a_missing_value_is_request_validation() -> None:
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        response = await http.put(URL, json={})

    _problem(response, 422, "request-validation")


async def test_put_unknown_field_is_request_validation() -> None:
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        response = await http.put(URL, json={"stale_days": 7, "long_stay_days": 30})

    _problem(response, 422, "request-validation")


async def test_put_without_the_csrf_header_is_403_csrf_before_the_role_check() -> None:
    async with _client(FakeUseCases(), role=Role.SALES, csrf=False) as http:
        response = await http.put(URL, json={"stale_days": 7})

    _problem(response, 403, "csrf")


# ---- 인증 ----


async def test_unauthenticated_is_401() -> None:
    async with _client(FakeUseCases()) as http:
        responses = [await http.get(URL), await http.put(URL, json={"stale_days": 7})]

    for response in responses:
        _problem(response, 401, "unauthenticated")
