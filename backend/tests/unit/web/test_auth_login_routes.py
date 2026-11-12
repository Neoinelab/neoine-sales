"""로그인·로그아웃·내 정보 라우터(AU): Fake 유스케이스 위에서 HTTP 계약을 확인한다.

세션 쿠키 속성, 입력 검증(422), AD 장애 응답(503), 폐지 경로, 비밀 비노출, openapi 문서화.
유스케이스 규칙 자체는 tests/unit/application/test_directory_login*.py 등이 맡는다.
"""

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.ports.directory import (
    DirectoryError,
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    VerificationStage,
)
from app.domain.auth.principal import Role
from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import CSRF_HEADER, make_settings
from tests.support.auth_seed import DUMMY_PASSWORD
from tests.support.openapi_spec import app_contract, operation_of
from tests.unit.web.local_account_http import (
    CONFIG,
    LOGIN,
    ME,
    SESSION_COOKIE,
    UNUSED_DATABASE_URL,
    problem,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import Response

LOGOUT = "/api/v1/auth/logout"
LOGIN_FAILED = "아이디 또는 비밀번호가 올바르지 않습니다"
OUTAGE_DETAIL = "인증 서버(AD)에 연결할 수 없습니다. 잠시 후 다시 시도하세요"
LEAK = "ldap-server-internal-detail"
LOGIN_KEYS = {"user_id", "subject", "email", "name", "role", "directory_warning"}
ME_KEYS = {"user_id", "subject", "email", "name", "role"}


@asynccontextmanager
async def client_of(
    use_cases: FakeUseCases, cookies: dict[str, str] | None = None, **settings: object
) -> AsyncIterator[AsyncClient]:
    """CSRF 헤더를 단 클라이언트. settings로 앱 설정(cookie_secure 등)을 바꾼다."""
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL, **settings), use_cases=use_cases)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies=cookies or {},
    ) as http:
        yield http


async def directory_system() -> FakeUseCases:
    """AD 설정이 있고 AD 계정이 있는 sales kim이 등록된 시스템."""
    use_cases = FakeUseCases()
    await use_cases.seed_directory()
    await use_cases.seed_user("kim", Role.SALES)
    use_cases.directory.add_account("kim", "pw-kim", display_name="김영업", email="kim@corp.test")
    return use_cases


async def post_login(
    http: AsyncClient,
    login_id: str = "kim",
    password: str = "pw-kim",  # noqa: S107 - 가짜 값
) -> Response:
    return await http.post(LOGIN, json={"login_id": login_id, "password": password})


def cookie_parts(response: Response) -> list[str]:
    """응답의 세션 쿠키 Set-Cookie 한 줄을 속성 단위(소문자)로 나눈다."""
    (line,) = response.headers.get_list("set-cookie")
    return [part.strip().lower() for part in line.split(";")]


async def test_login_returns_200_with_an_http_only_lax_session_cookie() -> None:
    """등록된 사용자가 AD 비밀번호로 로그인하면 200과 HttpOnly·Lax 세션 쿠키를 받는다.

    테스트 코드: AU-001
    """
    # given: AD 계정이 있는 등록된 sales kim (cookie_secure는 local 기본값 꺼짐)
    use_cases = await directory_system()
    async with client_of(use_cases) as http:
        # when: kim이 로그인한다
        response = await post_login(http)
        me = await http.get(ME)

    # then: 200 본문과 HttpOnly·Lax·Path=/·8시간 쿠키(Secure 없음)이고 내 정보가 열린다
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == LOGIN_KEYS
    assert (body["subject"], body["role"], body["name"], body["email"]) == (
        "kim",
        "sales",
        "김영업",
        "kim@corp.test",
    )
    assert body["directory_warning"] is None
    parts = cookie_parts(response)
    assert parts[0].startswith(f"{SESSION_COOKIE}=")
    assert {"httponly", "samesite=lax", "path=/", "max-age=28800"} <= set(parts)
    assert "secure" not in parts
    assert me.status_code == 200


async def test_login_cookie_is_secure_when_the_deployment_requires_it() -> None:
    """cookie_secure가 켜져 있으면 세션 쿠키에 Secure가 붙는다.

    테스트 코드: AU-002
    """
    # given: cookie_secure가 켜진 배포와 등록된 kim
    use_cases = await directory_system()
    async with client_of(use_cases, cookie_secure=True) as http:
        # when: kim이 로그인한다
        response = await post_login(http)

    # then: 세션 쿠키에 Secure 속성이 있다
    assert response.status_code == 200
    assert "secure" in cookie_parts(response)


async def test_login_sets_no_cookie_other_than_the_session_cookie() -> None:
    """로그인 응답은 세션 쿠키 말고 다른 쿠키를 심지 않는다.

    테스트 코드: AU-003
    """
    # given: AD 계정이 있는 등록된 kim
    use_cases = await directory_system()
    async with client_of(use_cases) as http:
        # when: kim이 로그인한다
        response = await post_login(http)

    # then: Set-Cookie는 세션 쿠키 하나뿐이다(폐지된 neoine_login 없음)
    lines = response.headers.get_list("set-cookie")
    assert len(lines) == 1
    assert lines[0].startswith(f"{SESSION_COOKIE}=")
    assert "neoine_login" not in "".join(lines)


@pytest.mark.parametrize("password", ["", "   ", "pw\u0000kim"])
async def test_empty_blank_or_nul_password_is_the_common_401_and_is_not_counted(
    password: str,
) -> None:
    """빈 값·공백·NUL 비밀번호는 401이고 AD를 부르지 않으며 시도에 세지 않는다.

    테스트 코드: AU-017
    """
    # given: AD 계정이 있는 등록된 kim
    use_cases = await directory_system()
    async with client_of(use_cases) as http:
        # when: 빈 값·공백·NUL이 든 비밀번호로 로그인한다
        response = await post_login(http, password=password)

    # then: 공통 실패 401, 쿠키 없음, AD 호출 없음, 실패 횟수 기록 없음
    assert problem(response, 401, "unauthenticated")["detail"] == LOGIN_FAILED
    assert "set-cookie" not in response.headers
    assert use_cases.directory.authenticate_calls == []
    assert use_cases.uow.login_failures._items == {}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"login_id": "kim"},
        {"password": "pw-kim"},
        {"login_id": "kim", "password": "x", "role": "admin"},
    ],
    ids=["empty", "no-password", "no-login-id", "extra-field"],
)
async def test_login_body_with_missing_or_unknown_fields_is_422(body: dict[str, str]) -> None:
    """필드가 빠졌거나 모르는 필드가 있는 로그인 본문은 422 request-validation이다.

    테스트 코드: AU-018
    """
    # given: AD 계정이 있는 등록된 kim
    use_cases = await directory_system()
    async with client_of(use_cases) as http:
        # when: 잘못된 본문으로 로그인한다
        response = await http.post(LOGIN, json=body)

    # then: 422 request-validation이고 AD를 부르지 않으며 시도에 세지 않는다
    problem(response, 422, "request-validation")
    assert use_cases.directory.authenticate_calls == []
    assert use_cases.uow.login_failures._items == {}


@pytest.mark.parametrize("field", ["password", "login_id"])
async def test_oversized_login_values_are_422_without_echoing_them(field: str) -> None:
    """너무 긴 아이디·비밀번호는 422이고 입력값을 응답에 되돌리지 않는다.

    테스트 코드: AU-019
    """
    # given: AD 계정이 있는 kim, 상한(아이디 128자, 비밀번호 256자)을 넘는 값
    use_cases = await directory_system()
    oversized = {"password": DUMMY_PASSWORD + "p" * 300, "login_id": "i" * 129}
    body = {"login_id": "kim", "password": "pw-kim"} | {field: oversized[field]}
    async with client_of(use_cases) as http:
        # when: 상한을 넘은 값으로 로그인한다
        response = await http.post(LOGIN, json=body)

    # then: 422이고 응답 본문에 입력값(비밀번호 포함)이 없다
    body_422 = problem(response, 422, "request-validation")
    assert oversized[field] not in response.text
    assert DUMMY_PASSWORD not in response.text
    assert "input" not in str(body_422["errors"])


async def test_login_values_at_the_upper_length_limit_pass_validation() -> None:
    """상한 길이의 값은 검증을 통과한다(256자 비밀번호는 로그인되고 128자 아이디는 형식 오류 401).

    테스트 코드: AU-019
    """
    # given: 256자 비밀번호의 AD 계정을 가진 등록된 kim
    use_cases = await directory_system()
    use_cases.directory.add_account("kim", "p" * 256)
    async with client_of(use_cases) as http:
        # when: 256자 비밀번호로, 그리고 128자 아이디로 로그인한다
        long_password = await post_login(http, password="p" * 256)
        long_id = await post_login(http, login_id="k" * 128)

    # then: 256자 비밀번호는 200, 128자 아이디는 422가 아니라 공통 실패 401이다
    assert long_password.status_code == 200
    assert long_id.status_code == 401


@pytest.mark.parametrize(
    "error",
    [
        DirectoryUnavailableError(LEAK, stage=VerificationStage.CONNECT),
        DirectoryUnavailableError(LEAK, stage=VerificationStage.TLS),
        DirectoryMisconfiguredError(LEAK, stage=VerificationStage.SEARCH),
    ],
    ids=["connect", "tls", "search"],
)
async def test_directory_outage_without_a_stored_hash_is_503_with_a_fixed_message(
    error: DirectoryError,
) -> None:
    """AD 장애 원인이 달라도 503 문구는 같고 원인을 드러내지 않는다.

    테스트 코드: AU-033
    """
    # given: AD가 원인 문구가 든 오류로 응답하지 못하고 kim에게는 저장된 해시가 없다
    use_cases = await directory_system()
    use_cases.directory.authenticate_fails_with = error
    async with client_of(use_cases) as http:
        # when: kim이 로그인한다
        response = await post_login(http)

    # then: 503 directory-unavailable과 고정 문구이고 원인 문구·쿠키가 없다
    assert problem(response, 503, "directory-unavailable")["detail"] == OUTAGE_DETAIL
    assert LEAK not in response.text
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_me_returns_the_five_values_of_the_users_row_for_every_role(role: Role) -> None:
    """내 정보는 세 역할 모두 자기 users 행의 다섯 값을 받는다.

    테스트 코드: AU-059
    """
    # given: 역할별 사용자 행과 그 사용자의 세션
    use_cases = FakeUseCases()
    user = await use_cases.seed_user("who", role, display_name="이름 하나")
    token = await use_cases.issue_session_for(user.to_principal())
    async with client_of(use_cases, {SESSION_COOKIE: token}) as http:
        # when: 내 정보를 조회한다
        response = await http.get(ME)

    # then: 키가 정확히 다섯이고 값이 users 행 기준이다
    assert response.status_code == 200
    assert set(response.json()) == ME_KEYS
    assert response.json() == {
        "user_id": user.id,
        "subject": "who",
        "email": None,
        "name": "이름 하나",
        "role": role.value,
    }


async def test_logout_revokes_the_session_and_clears_the_cookie() -> None:
    """로그아웃하면 세션이 폐기되고 쿠키가 지워져 이후 요청은 401이다.

    테스트 코드: AU-060
    """
    # given: 로그인한 kim과 그 세션 토큰
    use_cases = await directory_system()
    async with client_of(use_cases) as http:
        login = await post_login(http)
        token = http.cookies[SESSION_COOKIE]
        assert login.status_code == 200
        # when: 로그아웃한다
        response = await http.post(LOGOUT)
    async with client_of(use_cases, {SESSION_COOKIE: token}) as same_token:
        after = await same_token.get(ME)

    # then: 204와 만료 Set-Cookie(Path=/)이고, 같은 토큰으로는 더 이상 인증되지 않는다
    assert response.status_code == 204
    parts = cookie_parts(response)
    assert "max-age=0" in parts
    assert "path=/" in parts
    assert problem(after, 401, "unauthenticated")["detail"] == "로그인이 필요합니다"


@pytest.mark.parametrize("case", ["no-cookie", "unknown-token", "already-revoked"])
async def test_logout_without_a_usable_session_is_a_harmless_204(case: str) -> None:
    """세션이 없거나 모르는·폐기된 토큰으로 로그아웃해도 204이고 무해하다.

    테스트 코드: AU-061
    """
    # given: 쿠키가 없거나, 발급한 적 없는 토큰이거나, 이미 로그아웃한 토큰
    use_cases = await directory_system()
    cookies: dict[str, str] = {}
    if case == "unknown-token":
        cookies = {SESSION_COOKIE: "made-up-token"}
    elif case == "already-revoked":
        user = await use_cases.seed_user("lee", Role.USER)
        token = await use_cases.issue_session_for(user.to_principal())
        async with client_of(use_cases, {SESSION_COOKIE: token}) as first:
            await first.post(LOGOUT)
        cookies = {SESSION_COOKIE: token}
    async with client_of(use_cases, cookies) as http:
        # when: 로그아웃한다
        response = await http.post(LOGOUT)

    # then: 204이고 세션 쿠키 삭제 응답이 온다
    assert response.status_code == 204
    assert "max-age=0" in cookie_parts(response)


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("GET", "/api/v1/auth/login", {404, 405}),
        ("GET", "/api/v1/auth/callback", {404}),
        ("POST", "/api/v1/auth/dev-login", {404}),
    ],
    ids=["login-get", "oidc-callback", "dev-login"],
)
async def test_retired_dev_login_and_oidc_routes_do_not_exist(
    method: str, path: str, allowed: set[int]
) -> None:
    """폐지된 개발용 로그인·OIDC 경로는 없는 경로이고 어디로도 리다이렉트하지 않는다.

    테스트 코드: AU-064
    """
    # given: 인증 설정이 없는 새 시스템
    async with client_of(FakeUseCases()) as http:
        # when: 폐지된 경로를 부른다
        response = await http.request(method, path, params={"code": "c"})

    # then: 없는 경로(404 또는 405)이고 Location·세션 쿠키가 없다
    assert response.status_code in allowed
    assert "location" not in response.headers
    assert "set-cookie" not in response.headers


async def test_auth_config_is_public_with_exactly_the_five_keys() -> None:
    """인증 설정 조회는 로그인 없이 200이고 키는 정확히 다섯이다.

    테스트 코드: AU-062
    """
    # given: 인증 설정이 없는 새 시스템, 로그인하지 않은 클라이언트
    async with client_of(FakeUseCases()) as http:
        # when: 인증 설정을 조회한다
        response = await http.get(CONFIG)

    # then: 200이고 directory_login·세 단계 플래그·auth_mode 다섯 키뿐이다(dev_login 없음)
    assert response.status_code == 200
    assert set(response.json()) == {
        "directory_login",
        "needs_directory_setup",
        "needs_storage_setup",
        "needs_admin_setup",
        "auth_mode",
    }


async def test_password_never_appears_in_responses_or_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """성공·실패·검증 오류·AD 장애(대체 로그인 성공·실패) 어디에도 비밀번호가 없다.

    테스트 코드: AU-065
    """
    # given: 비밀번호가 더미 값인 AD 계정 kim, 로그 수준 DEBUG
    caplog.set_level(logging.DEBUG)
    use_cases = await directory_system()
    use_cases.directory.add_account("kim", DUMMY_PASSWORD)
    async with client_of(use_cases) as http:
        # when: 성공, 실패, 검증 오류, 장애 중 대체 로그인 성공·실패 순서로 같은 비밀번호를 낸다
        responses = [
            await post_login(http, "kim", DUMMY_PASSWORD),
            await post_login(http, "ghost", DUMMY_PASSWORD),
            await post_login(http, "kim", DUMMY_PASSWORD + "p" * 300),
        ]
        use_cases.directory.authenticate_fails_with = DirectoryUnavailableError(
            stage=VerificationStage.CONNECT
        )
        responses += [
            await post_login(http, "kim", DUMMY_PASSWORD),
            await post_login(http, "ghost", DUMMY_PASSWORD),
        ]

    # then: 상태는 200·401·422·200·503이고 어떤 응답 본문·헤더·로그에도 비밀번호가 없다
    assert [r.status_code for r in responses] == [200, 401, 422, 200, 503]
    for response in responses:
        assert DUMMY_PASSWORD not in response.text
        assert DUMMY_PASSWORD not in str(response.headers)
    assert DUMMY_PASSWORD not in caplog.text


def test_openapi_documents_the_login_errors_and_the_password_field() -> None:
    """openapi는 로그인 오류 응답과 비밀번호 칸 표기를 문서화한다.

    테스트 코드: AU-066
    """
    # given: 앱이 만드는 openapi 계약
    spec = app_contract()
    login_codes = set(operation_of(spec, "post", "/api/v1/auth/login")["responses"])
    me_codes = set(operation_of(spec, "get", "/api/v1/auth/me")["responses"])
    schemas = spec["components"]["schemas"]
    # when: 로그인·내 정보 경로와 로그인 요청·응답 스키마를 읽는다
    password = schemas["LoginRequest"]["properties"]["password"]

    # then: 오류 응답 여섯 개와 내 정보 401이 있고, 비밀번호는 password·writeOnly이며 응답에 없다
    assert {"200", "401", "409", "422", "429", "503"} <= login_codes
    assert "401" in me_codes
    assert password["format"] == "password"
    assert password["writeOnly"] is True
    assert not [name for name in schemas["LoginResponse"]["properties"] if "password" in name]


def test_openapi_has_no_dev_login_path_or_schema() -> None:
    """공개된 API 계약에 개발용 로그인 경로와 요청 스키마가 없다.

    테스트 코드: AU-064
    """
    # when: 경로와 스키마 이름을 읽는다 (전제: 앱이 만드는 openapi 계약)
    spec = app_contract()

    # then: dev-login 경로와 DevLoginRequest 스키마가 없다
    assert "/api/v1/auth/dev-login" not in spec["paths"]
    assert "DevLoginRequest" not in spec["components"]["schemas"]
