"""플랫폼 공통(PL) 단위 테스트 도우미: 역할별 클라이언트와 Problem 단언.

FakeUseCases 위의 앱 하나를 익명·admin(BOSS)·sales(KIM)·user(VIEWER) 클라이언트가 함께 쓴다.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.support.permission_table import Route, concrete_path, garbage_body, request_body
from tests.unit.web.saved_report_http import clients

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import AsyncClient, Response

PROBLEM_PREFIX = "https://neoine-sales.example/problems/"
PROBLEM_CONTENT_TYPE = "application/problem+json"
ROLE_USERS = {"anon": Role.USER, "boss": Role.ADMIN, "kim": Role.SALES, "viewer": Role.USER}
ANONYMOUS, BOSS, KIM, VIEWER = "anon", "boss", "kim", "viewer"
LOGIN_REQUIRED = "로그인이 필요합니다"
WRITE_DENIED = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"
ADMIN_DENIED = "관리자 권한이 필요합니다"
CSRF_DETAIL = "요청 헤더(X-Requested-With)가 필요합니다"


@asynccontextmanager
async def role_clients(
    use_cases: FakeUseCases | None = None, *, csrf: bool = True
) -> AsyncIterator[dict[str, AsyncClient]]:
    """익명(anon)·BOSS(admin)·KIM(sales)·VIEWER(user) 클라이언트."""
    async with clients(use_cases or FakeUseCases(), ROLE_USERS, csrf=csrf) as made:
        yield made


async def call_route(http: AsyncClient, route: Route, *, garbage: bool = False) -> Response:
    """권한 표 경로를 없는 id와 빈 본문(또는 잘못된 본문)으로 부른다."""
    method, path = route
    body = garbage_body(method) if garbage else request_body(method)
    return await http.request(method, concrete_path(path), json=body)


def problem_of(response: Response) -> dict[str, Any]:
    """Problem 응답이면 본문을, 아니면 AssertionError를 낸다."""
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE), response.text
    body: dict[str, Any] = response.json()
    return body


def kind_of(response: Response) -> str:
    """Problem `type`에서 공통 접두사를 뗀 종류 이름(예: `forbidden`)."""
    return str(problem_of(response)["type"]).removeprefix(PROBLEM_PREFIX)


def then_problem_is(response: Response, status: int, kind: str) -> dict[str, Any]:
    """상태 코드·Problem 형식·종류가 모두 맞는 Problem 본문을 돌려준다."""
    assert response.status_code == status, response.text
    body = problem_of(response)
    assert kind_of(response) == kind, body
    return body
