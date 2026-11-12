"""모든 API 경로는 권한 표대로만 열려 있다(PL-002~PL-009). 표는 `tests/support/permission_table.py`.

FakeUseCases 위의 앱을 익명·BOSS(admin)·KIM(sales)·VIEWER(user)가 부른다. 경로 템플릿의 id 자리는
형식은 맞지만 없는 값으로 채우므로, 허용된 역할의 응답은 그 feature의 404·422 등이다.
"""

from typing import TYPE_CHECKING

from app.domain.auth.principal import Role
from tests.support.openapi_spec import api_routes_of, app_contract
from tests.support.permission_table import (
    ADMIN_ONLY,
    ADMINS,
    BUSINESS_WRITES,
    EXPECTED,
    LOGGED_IN_ANY,
    REPORT_ROUTES,
    Route,
    protected_routes,
)
from tests.unit.web.platform_http import (
    ANONYMOUS,
    BOSS,
    KIM,
    LOGIN_REQUIRED,
    VIEWER,
    WRITE_DENIED,
    call_route,
    kind_of,
    problem_of,
    role_clients,
)
from tests.unit.web.saved_report_http import create_body

if TYPE_CHECKING:
    from httpx import Response

ROLE_OF = {BOSS: "admin", KIM: "sales", VIEWER: "user"}


def test_permission_table_covers_every_endpoint_of_the_app() -> None:
    """앱이 공개한 모든 엔드포인트가 권한 표에 있고 표에만 있는 엔드포인트는 없다.

    테스트 코드: PL-002
    """
    # given: 앱이 만든 OpenAPI 계약
    contract = app_contract()
    # when: 계약의 (메서드, 경로) 집합을 권한 표의 키와 비교한다
    actual = api_routes_of(contract)
    # then: 두 집합이 같고 관리자 전용 행은 admin만, 업무 쓰기 행에는 user가 없다
    assert actual - set(EXPECTED) == set(), "권한 표(permission_table.py)에 없는 엔드포인트"
    assert set(EXPECTED) - actual == set(), "표에는 있지만 앱에 없는 엔드포인트"
    assert {EXPECTED[route] for route in ADMIN_ONLY} == {ADMINS}
    assert all(Role.USER not in (EXPECTED[route] or ()) for route in BUSINESS_WRITES)


async def test_anonymous_requests_to_protected_routes_are_all_401() -> None:
    """로그인하지 않고 보호 경로를 부르면 모두 401이다.

    테스트 코드: PL-003
    """
    wrong: dict[Route, str] = {}
    # given: 익명(세션 쿠키 없음, CSRF 헤더 있음)
    async with role_clients() as c:
        # when: 권한 표의 보호 경로를 하나씩 빈 본문으로 부른다
        for route in protected_routes():
            response = await call_route(c[ANONYMOUS], route)
            # then: 모두 401 unauthenticated "로그인이 필요합니다"다
            if (
                response.status_code != 401
                or kind_of(response) != "unauthenticated"
                or problem_of(response)["detail"] != LOGIN_REQUIRED
            ):
                wrong[route] = f"{response.status_code} {response.text[:80]}"
    assert wrong == {}


async def test_allowed_roles_are_never_stopped_by_the_role_guard() -> None:
    """허용된 역할은 어느 보호 경로에서도 역할 가드에 막히지 않는다.

    테스트 코드: PL-004
    """
    blocked: dict[str, str] = {}
    async with role_clients() as c:
        # given: 권한 표에서 그 경로를 허용하는 역할로 로그인
        for route in protected_routes():
            for name, role in ROLE_OF.items():
                if role not in {r.value for r in EXPECTED[route] or ()}:
                    continue
                # when: 경로를 없는 id와 빈 본문으로 부른다
                response = await call_route(c[name], route)
                # then: 응답이 401도 403도 아니다
                if response.status_code in {401, 403}:
                    blocked[f"{route} as {role}"] = f"{response.status_code} {response.text[:80]}"
    assert blocked == {}


async def test_user_on_business_write_routes_gets_the_read_only_403() -> None:
    """user가 업무 쓰기 경로를 부르면 읽기 전용 403이다.

    테스트 코드: PL-005
    """
    wrong: dict[Route, str] = {}
    # given: VIEWER(user)
    async with role_clients() as c:
        # when: 권한 표의 업무 쓰기 경로를 하나씩 부른다
        for route in BUSINESS_WRITES:
            response = await call_route(c[VIEWER], route)
            # then: 모두 403 forbidden "이 작업을 할 권한이 없습니다(읽기 전용 계정)"다
            if (
                response.status_code != 403
                or kind_of(response) != "forbidden"
                or problem_of(response)["detail"] != WRITE_DENIED
            ):
                wrong[route] = f"{response.status_code} {response.text[:80]}"
    assert wrong == {}


async def test_user_write_rejection_comes_before_body_validation_and_lookup() -> None:
    """user의 쓰기 거절은 본문 검증·존재 확인보다 먼저다.

    테스트 코드: PL-006
    """
    wrong: dict[Route, str] = {}
    # given: VIEWER
    async with role_clients() as c:
        # when: 업무 쓰기 경로를 형식이 틀린 본문과 없는 id로 부른다
        for route in BUSINESS_WRITES:
            response = await call_route(c[VIEWER], route, garbage=True)
            # then: 422·404가 아니라 403 forbidden이다
            if response.status_code != 403 or kind_of(response) != "forbidden":
                wrong[route] = f"{response.status_code} {response.text[:80]}"
    assert wrong == {}


def _admin_denied_ok(response: Response, *, role: str) -> bool:
    """403 forbidden이고 문구가 관리자 문구(또는 user의 읽기 전용 문구)다."""
    if response.status_code != 403 or kind_of(response) != "forbidden":
        return False
    detail = str(problem_of(response)["detail"])
    return "관리자" in detail or (role == "user" and detail == WRITE_DENIED)


async def test_non_admins_on_admin_only_routes_get_403() -> None:
    """admin이 아닌 사용자가 관리자 전용 경로를 부르면 403이다.

    테스트 코드: PL-007
    """
    wrong: dict[str, str] = {}
    # given: KIM(sales), VIEWER(user)
    async with role_clients() as c:
        # when: 각자 권한 표의 관리자 전용 경로를 하나씩 부른다
        for route in ADMIN_ONLY:
            for name in (KIM, VIEWER):
                response = await call_route(c[name], route)
                # then: 모두 403 forbidden이고 문구는 관리자 문구(user는 읽기 전용 문구도 가능)다
                if not _admin_denied_ok(response, role=ROLE_OF[name]):
                    wrong[f"{route} as {ROLE_OF[name]}"] = (
                        f"{response.status_code} {response.text[:80]}"
                    )
    assert wrong == {}


async def test_sales_admin_route_rejection_comes_before_body_validation() -> None:
    """sales의 관리자 경로 거절은 본문 검증보다 먼저이고 문구에 '관리자'가 있다.

    테스트 코드: PL-008
    """
    wrong: dict[Route, str] = {}
    # given: KIM(sales)
    async with role_clients() as c:
        # when: 관리자 전용 경로를 형식이 틀린 본문으로 부른다
        for route in ADMIN_ONLY:
            response = await call_route(c[KIM], route, garbage=True)
            # then: 422가 아니라 403 forbidden이고 detail에 "관리자"가 있다
            if not _admin_denied_ok(response, role="sales") or "관리자" not in str(
                problem_of(response)["detail"]
            ):
                wrong[route] = f"{response.status_code} {response.text[:80]}"
    assert wrong == {}


async def test_write_routes_without_a_role_guard_do_not_reject_user() -> None:
    """역할 가드가 없는 쓰기 경로는 user도 403이 아니다.

    테스트 코드: PL-009
    """
    async with role_clients() as c:
        http = c[VIEWER]
        # given: VIEWER
        created = await http.post("/api/v1/reports", json=create_body())
        queried = await http.post(
            "/api/v1/reports/query", json={"columns": [{"field": "deal.code"}]}
        )
        profile = await http.patch("/api/v1/me/profile", json={})
        report_routes = [route for route in REPORT_ROUTES if route[0] != "GET"]
        # when: 저장 리포트 쓰기, 리포트 조회 실행, 내 정보 수정을 부른다
        others = [await call_route(http, route) for route in [*report_routes, *LOGGED_IN_ANY]]
    # then: 역할 가드의 403이 아니다(리포트 생성 201, 조회 실행 200)
    assert created.status_code == 201, created.text
    assert queried.status_code == 200, queried.text
    assert profile.status_code != 403, profile.text
    assert [r.text for r in others if WRITE_DENIED in r.text] == []
