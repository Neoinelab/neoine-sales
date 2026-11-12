"""경고 기준 라우터: FakeUseCases 위의 HTTP 계약과 판정 순서(401, csrf, 403, 422).

DB 없이 라우터·스키마·오류 매핑·권한을 빠르게 확인하는 단위 테스트다. 유스케이스 규칙은
`application/test_alert_settings.py`(BDD 케이스)가 맡는다.
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
from tests.support.app_settings import CSRF_HEADER, make_settings

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
    """저장한 적이 없으면 모든 역할이 14일과 빈 저장 기록을 읽는다.

    테스트 코드: RK-043
    """
    # given: 저장한 적이 없고 admin·sales·user 중 하나로 로그인했다
    async with _client(FakeUseCases(), role=role) as http:
        # when: 경고 기준을 조회한다
        response = await http.get(URL)

    # then: 200 {stale_days: 14, updated_at: null, updated_by: null}이다
    assert response.status_code == 200, response.text
    assert response.json() == {"stale_days": 14, "updated_at": None, "updated_by": None}


async def test_get_after_an_admin_saved_shows_the_value_the_time_and_the_saver() -> None:
    """admin이 저장한 뒤 조회하면 값·시각·저장자가 보인다.

    테스트 코드: RK-044
    """
    # given: admin이 30일로 저장했다
    use_cases = FakeUseCases()
    async with _client(use_cases, role=Role.ADMIN) as http:
        await http.put(URL, json={"stale_days": 30})
        # when: 경고 기준을 조회한다
        body = (await http.get(URL)).json()
        me = (await http.get("/api/v1/auth/me")).json()

    # then: 키는 stale_days·updated_at·updated_by뿐이고 30일·저장 시각·저장한 admin이 보인다
    assert set(body) == RESPONSE_KEYS
    assert body["stale_days"] == 30
    assert body["updated_at"] is not None
    assert body["updated_by"]["id"] == me["user_id"]
    assert set(body["updated_by"]) == {"id", "name", "resigned", "label", "role"}


# ---- PUT ----


async def test_put_by_admin_returns_the_saved_result() -> None:
    """admin이 저장하면 200과 저장 결과를 준다.

    테스트 코드: RK-044
    """
    # given: admin으로 로그인했다
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        # when: 7일로 저장한다
        response = await http.put(URL, json={"stale_days": 7})

    # then: 200이고 키는 셋뿐이며 stale_days가 7이고 저장자가 퇴사가 아니다
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == RESPONSE_KEYS
    assert body["stale_days"] == 7
    assert body["updated_by"]["resigned"] is False


@pytest.mark.parametrize("days", [1, 365])
async def test_put_accepts_the_bounds(days: int) -> None:
    """경계값 1일과 365일은 저장된다.

    테스트 코드: RK-045
    """
    # given: admin으로 로그인했다
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        # when: 경계값을 저장한다
        response = await http.put(URL, json={"stale_days": days})

    # then: 200이고 값이 그대로 나온다
    assert response.status_code == 200, response.text
    assert response.json()["stale_days"] == days


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_put_by_sales_or_user_is_forbidden_and_saves_nothing(role: Role) -> None:
    """sales·user의 변경은 403이고 값은 그대로다.

    테스트 코드: RK-048
    """
    # given: sales 또는 user로 로그인했다
    use_cases = FakeUseCases()
    async with _client(use_cases, role=role) as http:
        # when: 7일로 저장하려 한다
        response = await http.put(URL, json={"stale_days": 7})
        current = await http.get(URL)

    # then: 403 forbidden(admin 전용 문구)이고 값은 14일 그대로다
    assert _problem(response, 403, "forbidden")["detail"] == ADMIN_DENIED
    assert current.json()["stale_days"] == 14


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_put_by_a_non_admin_with_a_bad_body_is_still_403(role: Role) -> None:
    """본문이 틀려도 sales·user의 변경은 403이다.

    테스트 코드: RK-048
    """
    # given: sales 또는 user로 로그인했다
    async with _client(FakeUseCases(), role=role) as http:
        # when: 형식이 틀린 본문으로 변경한다
        response = await http.put(URL, json={"garbage": 1})

    # then: 422가 아니라 403 forbidden이다
    _problem(response, 403, "forbidden")


@pytest.mark.parametrize("days", [0, 366, -1])
async def test_put_out_of_range_is_invalid_value_and_keeps_the_stored_value(days: int) -> None:
    """범위 밖 정수는 422 invalid-value 고정 문구이고 저장된 값은 그대로다.

    테스트 코드: RK-046
    """
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        # given: admin이 21일로 저장해 두었다
        await http.put(URL, json={"stale_days": 21})
        # when: 범위 밖 값으로 저장한다
        response = await http.put(URL, json={"stale_days": days})
        current = await http.get(URL)

    # then: 422 invalid-value와 고정 문구이고 값은 21일 그대로다
    assert _problem(response, 422, "invalid-value")["detail"] == RANGE_MESSAGE
    assert current.json()["stale_days"] == 21


@pytest.mark.parametrize("value", ["7", 7.5, True, None, [7]])
async def test_put_string_or_float_or_bool_is_request_validation(value: object) -> None:
    """문자열·소수·bool·null·배열은 422 request-validation이고 값은 그대로다.

    테스트 코드: RK-047
    """
    # given: admin으로 로그인했다
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        # when: 정수가 아닌 값으로 저장하려 한다
        response = await http.put(URL, json={"stale_days": value})
        current = await http.get(URL)

    # then: 422 request-validation이고 값은 14일 그대로다
    _problem(response, 422, "request-validation")
    assert current.json()["stale_days"] == 14


async def test_put_with_a_missing_value_is_request_validation() -> None:
    """stale_days가 없으면 422 request-validation이다.

    테스트 코드: RK-047
    """
    # given: admin으로 로그인했다
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        # when: 빈 본문으로 저장하려 한다
        response = await http.put(URL, json={})

    # then: 422 request-validation이다
    _problem(response, 422, "request-validation")


async def test_put_unknown_field_is_request_validation() -> None:
    """모르는 필드가 있으면 422 request-validation이다.

    테스트 코드: RK-047
    """
    # given: admin으로 로그인했다
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        # when: 모르는 필드를 넣어 저장하려 한다
        response = await http.put(URL, json={"stale_days": 7, "long_stay_days": 30})

    # then: 422 request-validation이다
    _problem(response, 422, "request-validation")


async def test_put_without_the_csrf_header_is_403_csrf_before_the_role_check() -> None:
    """CSRF 헤더가 없으면 역할 확인보다 먼저 403 csrf다."""
    # given: sales로 로그인했고 CSRF 헤더가 없다
    async with _client(FakeUseCases(), role=Role.SALES, csrf=False) as http:
        # when: 저장하려 한다
        response = await http.put(URL, json={"stale_days": 7})

    # then: 403 csrf다
    _problem(response, 403, "csrf")


# ---- 인증 ----


async def test_unauthenticated_is_401() -> None:
    """로그인하지 않은 요청은 조회·변경 모두 401이다."""
    # given: 로그인하지 않은 클라이언트다
    async with _client(FakeUseCases()) as http:
        # when: 조회와 변경을 부른다
        responses = [await http.get(URL), await http.put(URL, json={"stale_days": 7})]

    # then: 둘 다 401 unauthenticated다
    for response in responses:
        _problem(response, 401, "unauthenticated")
