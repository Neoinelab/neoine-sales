"""CSRF 헤더(X-Requested-With) 검사와 판정 순서(PL-010~PL-015).

401(미인증) -> 403 csrf(상태 변경 메서드만) -> 403 역할 가드 순서를
FakeUseCases 위의 앱으로 확인한다.
"""

from tests.fakes.use_cases import FakeUseCases
from tests.support.permission_table import ADMIN_ONLY, BUSINESS_WRITES
from tests.unit.web.local_account_http import anonymous
from tests.unit.web.platform_http import (
    ANONYMOUS,
    BOSS,
    CSRF_DETAIL,
    KIM,
    LOGIN_REQUIRED,
    VIEWER,
    call_route,
    role_clients,
    then_problem_is,
)
from tests.unit.web.saved_report_http import create_body

CONFIG = "/api/v1/auth/config"
PUBLIC_WRITES = [
    ("POST", "/api/v1/auth/login", {"login_id": "kim", "password": "x"}),
    ("POST", "/api/v1/auth/logout", None),
    ("PUT", "/api/v1/auth/setup/auth-mode", {"mode": "local"}),
    ("PUT", "/api/v1/auth/setup/directory", {}),
    ("PUT", "/api/v1/auth/setup/storage", {"path": "/data/neoine/files"}),
    ("POST", "/api/v1/auth/setup/storage/test", {"path": "/data/neoine/files"}),
    ("POST", "/api/v1/auth/setup", {"login_id": "kim"}),
]
CONTACT = {"kind": "customer", "company": "네오인", "name": "김철수"}
NEW_USER = {"login_id": "park", "role": "sales", "display_name": "박영업"}


async def test_unauthenticated_request_is_401_even_without_the_csrf_header() -> None:
    """미인증 요청은 CSRF 헤더가 없어도 401이 먼저다.

    테스트 코드: PL-010
    """
    # given: 익명, CSRF 헤더 없음
    async with role_clients(csrf=False) as c:
        # when: 업무 쓰기 경로를 부른다
        response = await c[ANONYMOUS].post("/api/v1/deals", json={})
    # then: 403 csrf가 아니라 401 unauthenticated다
    body = then_problem_is(response, 401, "unauthenticated")
    assert body["detail"] == LOGIN_REQUIRED


async def test_signed_in_state_change_without_the_csrf_header_is_403_and_stores_nothing() -> None:
    """로그인한 사용자의 상태 변경 요청에 CSRF 헤더가 없으면 403 csrf이고 저장되지 않는다.

    테스트 코드: PL-011
    """
    use_cases = FakeUseCases()
    # given: KIM(sales)과 BOSS(admin)로 로그인, CSRF 헤더 없음
    async with role_clients(use_cases, csrf=False) as c:
        # when: 연락처 등록, 저장 리포트 생성·삭제, 사용자 등록을 보낸다
        responses = [
            await c[BOSS].post("/api/v1/contacts", json=CONTACT),
            await c[KIM].post("/api/v1/reports", json=create_body()),
            await c[KIM].delete("/api/v1/reports/1"),
            await c[BOSS].post("/api/v1/users", json=NEW_USER),
        ]
    # then: 모두 403 csrf이고 아무것도 저장되지 않는다
    for response in responses:
        body = then_problem_is(response, 403, "csrf")
        assert body["detail"] == CSRF_DETAIL
    async with role_clients(use_cases) as c:
        assert (await c[BOSS].get("/api/v1/contacts")).json()["total"] == 0
        assert (await c[KIM].get("/api/v1/reports")).json() == []
        logins = [u["login_id"] for u in (await c[BOSS].get("/api/v1/users")).json()["items"]]
        assert "park" not in logins


async def test_empty_csrf_header_value_is_the_same_as_no_header() -> None:
    """CSRF 헤더 값이 비어 있으면 헤더가 없는 것과 같다.

    테스트 코드: PL-012
    """
    # given: X-Requested-With가 빈 값
    async with role_clients() as c:
        # when: 상태 변경 요청(최초 설정 인증 방식 선택)을 보낸다
        response = await c[ANONYMOUS].request(
            "PUT",
            "/api/v1/auth/setup/auth-mode",
            json={"mode": "local"},
            headers={"X-Requested-With": ""},
        )
    # then: 403 csrf다
    then_problem_is(response, 403, "csrf")


async def test_read_requests_do_not_need_the_csrf_header() -> None:
    """조회 요청은 CSRF 헤더 없이도 된다.

    테스트 코드: PL-013
    """
    # given: KIM으로 로그인, CSRF 헤더 없음
    async with role_clients(csrf=False) as c:
        # when: 조회 요청을 보낸다
        response = await c[KIM].get("/api/v1/contacts/companies", params={"kind": "customer"})
    # then: 200이다
    assert response.status_code == 200, response.text


async def test_public_auth_routes_also_need_the_csrf_header() -> None:
    """공개 인증 경로(로그인·로그아웃·최초 설정)도 CSRF 헤더가 필요하다.

    테스트 코드: PL-014
    """
    async with anonymous(FakeUseCases()) as http:
        # given: 사용자가 없는 새 시스템의 익명 방문자, CSRF 헤더 없음
        no_header = {"X-Requested-With": ""}
        before = (await http.get(CONFIG)).json()
        # when: 로그인, 로그아웃, 최초 설정 각 단계를 부른다
        responses = [
            await http.request(method, path, json=body, headers=no_header)
            for method, path, body in PUBLIC_WRITES
        ]
        # then: 모두 403 csrf이고 저장이 없다(설정 상태 그대로)
        for response in responses:
            then_problem_is(response, 403, "csrf")
        config = (await http.get(CONFIG)).json()
    assert config == before
    assert config["auth_mode"] is None


async def test_csrf_check_comes_before_the_role_guard() -> None:
    """CSRF 검사는 역할 가드보다 먼저다.

    테스트 코드: PL-015
    """
    async with role_clients(csrf=False) as c:
        # given: VIEWER로 로그인(sales는 관리자 경로), CSRF 헤더 없음
        write = await call_route(c[VIEWER], BUSINESS_WRITES[2])
        # when: 업무 쓰기 경로와 관리자 전용 경로를 부른다
        admin = await call_route(c[KIM], ADMIN_ONLY[2])
    # then: kind가 forbidden이 아니라 csrf인 403이다
    then_problem_is(write, 403, "csrf")
    then_problem_is(admin, 403, "csrf")
