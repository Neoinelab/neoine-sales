"""세션·쿠키·개발용 로그인 step: 토큰으로 요청하기, 내 정보, 로그아웃, 쿠키 속성 확인."""

from typing import TYPE_CHECKING

from tests.functional.steps.auth import LOGIN, LOGOUT, ME, password_of

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

SESSION_COOKIE = "neoine_session"
DEV_LOGIN = "/api/v1/auth/dev-login"


def session_header(token: str) -> dict[str, str]:
    """쿠키 저장소와 별개로 특정 세션으로 요청하게 하는 헤더."""
    return {"Cookie": f"{SESSION_COOKIE}={token}"}


def session_cookie_header(response: Response) -> str:
    """응답의 Set-Cookie 중 세션 쿠키 한 줄."""
    found = [
        h for h in response.headers.get_list("set-cookie") if h.startswith(SESSION_COOKIE + "=")
    ]
    assert found, f"{SESSION_COOKIE} 쿠키가 없다: {response.headers.get_list('set-cookie')}"
    return found[0]


async def given_session_token(api: Api, *, login_id: str) -> str:
    """해당 사원이 로그인해 둔 세션의 토큰(쿠키 값). 쿠키 저장소도 그 세션으로 바뀐다."""
    body = {"login_id": login_id, "password": password_of(login_id)}
    response = await api.post(LOGIN, json=body)
    assert response.status_code == 200, response.text
    return response.cookies[SESSION_COOKIE]


async def given_session_works(api: Api, *, token: str) -> None:
    """그 세션으로 업무 API(Deal 목록)가 200이다."""
    response = await api.get("/api/v1/deals", headers=session_header(token))
    assert response.status_code == 200, response.text


async def when_log_out(api: Api) -> Response:
    return await api.post(LOGOUT)


async def when_get_me(api: Api) -> Response:
    return await api.get(ME)


async def when_get_with_session(api: Api, url: str, *, token: str) -> Response:
    """쿠키 저장소가 아니라 주어진 세션 토큰으로 GET 한다."""
    return await api.get(url, headers=session_header(token))


async def when_dev_login(api: Api, *, role: str) -> Response:
    return await api.post(DEV_LOGIN, json={"role": role})


def then_session_cookie_is_http_only_lax(response: Response) -> str:
    """세션 쿠키가 HttpOnly·SameSite=Lax·8시간·path=/·Secure 아님이다. 쿠키 헤더를 돌려준다."""
    cookie = session_cookie_header(response).lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=28800" in cookie
    assert "path=/" in cookie
    assert "secure" not in cookie.replace("samesite", "")
    return cookie


async def then_me_is(api: Api, **fields: object) -> None:
    """지금 쿠키 저장소의 세션으로 본 내 정보에 주어진 필드가 그 값으로 들어 있다."""
    response = await api.get(ME)
    assert response.status_code == 200, response.text
    body = response.json()
    assert {key: body.get(key) for key in fields} == fields, body


async def then_caller_is_anonymous(api: Api) -> None:
    assert (await api.get(ME)).status_code == 401
