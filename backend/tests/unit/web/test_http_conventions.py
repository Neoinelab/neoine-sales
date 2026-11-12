"""공통 HTTP 관례: Problem 형식, 요청 형식 오류, 404·405, 문서 노출, CORS.

PL-016·018~020·030~033. FakeUseCases 위의 앱을 쓴다(DB 접속 없음).
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import ALLOWED_ORIGIN, make_settings
from tests.support.openapi_spec import UNUSED_DATABASE_URL
from tests.unit.web.platform_http import (
    KIM,
    PROBLEM_CONTENT_TYPE,
    PROBLEM_PREFIX,
    role_clients,
    then_problem_is,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

MISSING_DEAL = "/api/v1/deals/20260101-ZZZZ"
SECRET = "SECRET-INPUT"  # noqa: S105 - 응답에 되돌려지면 안 되는 표시용 값


@asynccontextmanager
async def anonymous_app(*, enable_docs: bool = True) -> AsyncIterator[AsyncClient]:
    """문서 노출 설정을 고른 앱의 익명 클라이언트."""
    settings = make_settings(UNUSED_DATABASE_URL, enable_docs=enable_docs)
    app = create_app(settings=settings, use_cases=FakeUseCases())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def test_error_response_is_a_problem_with_the_request_path_as_instance() -> None:
    """오류 응답은 Problem 형식이고 instance는 요청 경로다.

    테스트 코드: PL-016
    """
    # given: KIM
    async with role_clients() as c:
        # when: 없는 Deal을 조회한다
        response = await c[KIM].get(MISSING_DEAL)
    # then: problem+json이고 type·title·status·detail·instance가 있다
    body = then_problem_is(response, 404, "not-found")
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    assert body["type"] == f"{PROBLEM_PREFIX}not-found"
    assert body["status"] == 404
    assert body["instance"] == MISSING_DEAL
    assert body["title"]
    assert body["detail"]


async def test_request_validation_error_lists_errors_without_echoing_the_input() -> None:
    """요청 형식 오류는 공통 문구와 오류 목록을 주고 입력값을 되돌리지 않는다.

    테스트 코드: PL-018
    """
    # given: KIM
    async with role_clients() as c:
        # when: 필수 칸이 빠지고 정수 칸에 표시용 문자열을 넣은 본문을 보낸다
        response = await c[KIM].post("/api/v1/deals", json={"users": SECRET})
    # then: 422 request-validation, 공통 문구, 항목은 loc·msg·type만 있고 입력값이 없다
    body = then_problem_is(response, 422, "request-validation")
    assert body["detail"] == "요청 형식이 올바르지 않습니다"
    assert body["errors"]
    for error in body["errors"]:
        assert {"loc", "msg", "type"} <= set(error)
        assert not {"input", "ctx", "url"} & set(error)
    assert SECRET not in response.text


async def test_unknown_route_is_a_404_problem() -> None:
    """없는 경로는 404 Problem이다.

    테스트 코드: PL-019
    """
    # given: KIM
    async with role_clients() as c:
        # when: 없는 경로를 조회한다
        response = await c[KIM].get("/api/v1/nothing-here")
    # then: 404, problem+json, status 404, kind http-error
    body = then_problem_is(response, 404, "http-error")
    assert body["status"] == 404
    assert body["detail"] == "Not Found"


async def test_wrong_method_is_a_405_problem() -> None:
    """허용되지 않은 메서드는 405 Problem이다.

    테스트 코드: PL-020
    """
    # given: KIM
    async with role_clients() as c:
        # when: 목록 경로에 허용되지 않은 PATCH를 보낸다
        response = await c[KIM].patch("/api/v1/users")
    # then: 405, problem+json, kind http-error이고 Allow 헤더가 그대로 붙는다
    body = then_problem_is(response, 405, "http-error")
    assert body["detail"] == "Method Not Allowed"
    assert response.headers["allow"]


async def test_docs_and_contract_are_open_when_docs_are_enabled() -> None:
    """문서 노출이 켜져 있으면 API 문서와 계약을 열 수 있다.

    테스트 코드: PL-030
    """
    # given: enable_docs가 true인 앱(로그인 없음)
    async with anonymous_app(enable_docs=True) as http:
        # when: /docs, /openapi.json을 연다
        docs = await http.get("/docs")
        contract = await http.get("/openapi.json")
    # then: 각각 200이다
    assert (docs.status_code, contract.status_code) == (200, 200)


async def test_docs_are_hidden_when_disabled_but_liveness_stays() -> None:
    """문서 노출이 꺼져 있으면 문서 경로는 404이고 생존 확인은 그대로다.

    테스트 코드: PL-031
    """
    # given: enable_docs가 false인 앱
    async with anonymous_app(enable_docs=False) as http:
        # when: 문서 세 경로와 /healthz를 연다
        hidden = [await http.get(path) for path in ("/docs", "/redoc", "/openapi.json")]
        liveness = await http.get("/healthz")
    # then: 문서 세 경로는 404, /healthz는 200이다
    assert [r.status_code for r in hidden] == [404, 404, 404]
    assert liveness.status_code == 200


async def test_cors_preflight_from_an_allowed_origin_is_allowed() -> None:
    """허용된 출처의 CORS 사전 요청은 허용된다.

    테스트 코드: PL-032
    """
    # given: cors_allowed_origins = [http://localhost:5173]
    async with anonymous_app() as http:
        # when: 그 출처로 POST 사전 요청(OPTIONS)을 보낸다
        response = await http.options(
            "/api/v1/users",
            headers={"Origin": ALLOWED_ORIGIN, "Access-Control-Request-Method": "POST"},
        )
    # then: 200이고 허용 출처가 그 출처다
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


async def test_cors_preflight_from_another_origin_has_no_allow_header() -> None:
    """허용되지 않은 출처에는 CORS 허용 헤더가 없다.

    테스트 코드: PL-033
    """
    # given: 같은 설정
    async with anonymous_app() as http:
        # when: https://evil.example 출처로 사전 요청을 보낸다
        response = await http.options(
            "/api/v1/users",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )
    # then: Access-Control-Allow-Origin 헤더가 없다
    assert "access-control-allow-origin" not in response.headers
