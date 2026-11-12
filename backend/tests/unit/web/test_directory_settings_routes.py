"""AD 설정 라우터(IN): Fake 유스케이스 위에서 HTTP 계약(상태·type·문구·권한·CSRF)을 확인한다.

DB 없이 라우터·스키마·오류 매핑을 보는 단위 테스트다. 유스케이스의 판정은
application 테스트가 맡는다.
"""

import logging
from typing import TYPE_CHECKING, Any

import pytest

from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)
from tests.factories_auth import BASE_DN, BIND_ACCOUNT, BIND_PASSWORD, USER_FILTER
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.platform_http import (
    ADMIN_DENIED,
    ANONYMOUS,
    BOSS,
    CSRF_DETAIL,
    KIM,
    LOGIN_REQUIRED,
    VIEWER,
    role_clients,
    then_problem_is,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from app.domain.common.secret import SealedSecret

DIRECTORY = "/api/v1/settings/directory"
DIRECTORY_TEST = "/api/v1/settings/directory/test"
STORAGE = "/api/v1/settings/storage"
STORAGE_TEST = "/api/v1/settings/storage/test"
BOSS_PASSWORD = "boss-pass"  # noqa: S105 - 가짜 값
NEW_BIND_PASSWORD = "new-pass"  # noqa: S105 - 가짜 값
WRONG_PASSWORD = "wrong-pass"  # noqa: S105 - 가짜 값
CONNECTION: dict[str, Any] = {
    "host": "dc1.corp.test",
    "port": 636,
    "security": "ssl",
    "bind_account": BIND_ACCOUNT,
    "user_filter": USER_FILTER,
    "connect_timeout_seconds": 5,
}
RESPONSE_KEYS = {
    "host",
    "port",
    "security",
    "bind_account",
    "bind_credential_status",
    "user_filter",
    "connect_timeout_seconds",
    "base_dn",
    "revision",
    "updated_at",
    "updated_by",
}
STAGE_MESSAGES = {
    "connect": "AD 서버에 연결하지 못했습니다. 호스트·포트·방화벽을 확인하세요",
    "tls": "TLS 연결에 실패했습니다. 보안 연결(SSL/StartTLS) 방식과 포트를 확인하세요",
    "service_bind": "바인드 계정으로 AD에 로그인하지 못했습니다. 계정과 비밀번호를 확인하세요",
    "base_dn": (
        "AD에서 Base DN(defaultNamingContext)을 찾지 못했습니다. 바인드 계정 권한을 확인하세요"
    ),
    "search": "사용자 조회에 실패했습니다. 사용자 필터를 확인하세요",
    "bind": "AD 인증에 실패했습니다. 관리자 비밀번호를 확인하세요",
}
FAILURES: dict[str, tuple[str, Exception]] = {
    "connect": ("discover", DirectoryUnavailableError(stage=VerificationStage.CONNECT)),
    "tls": ("discover", DirectoryUnavailableError(stage=VerificationStage.TLS)),
    "service_bind": ("discover", DirectoryMisconfiguredError(stage=VerificationStage.SERVICE_BIND)),
    "base_dn": ("discover", DirectoryMisconfiguredError(stage=VerificationStage.BASE_DN)),
    "search": ("authenticate", InvalidCredentialsError(stage=VerificationStage.SEARCH)),
    "bind": ("authenticate", InvalidCredentialsError(stage=VerificationStage.BIND)),
}


def _update_body(**extra: Any) -> dict[str, Any]:  # noqa: ANN401
    return {
        **CONNECTION,
        "bind_password": NEW_BIND_PASSWORD,
        "password": BOSS_PASSWORD,
        "expected_revision": 1,
        **extra,
    }


def _test_body(**extra: Any) -> dict[str, Any]:  # noqa: ANN401
    return {**CONNECTION, "bind_password": NEW_BIND_PASSWORD, "password": BOSS_PASSWORD, **extra}


async def _given_saved_settings() -> FakeUseCases:
    """예시 AD 설정(revision 1)이 저장되어 있고 Fake AD가 BOSS를 boss-pass로 인증한다."""
    use_cases = FakeUseCases()
    await use_cases.seed_directory()
    use_cases.directory.add_account("boss", BOSS_PASSWORD)
    return use_cases


async def _revision(http: AsyncClient) -> int:
    return int((await http.get(DIRECTORY)).json()["revision"])


async def test_admin_reads_the_settings_with_the_documented_keys_and_no_secret() -> None:
    """조회 응답은 문서화된 11개 키뿐이고 비밀번호·암호문이 없다.

    테스트 코드: IN-001
    """
    # given: BOSS가 저장해 revision 2가 된 AD 설정
    use_cases = await _given_saved_settings()
    async with role_clients(use_cases) as c:
        saved = await c[BOSS].put(DIRECTORY, json=_update_body())
        me = (await c[BOSS].get("/api/v1/auth/me")).json()
        # when: BOSS가 AD 설정을 조회한다
        response = await c[BOSS].get(DIRECTORY)

    # then: 키는 11개뿐, 상태 ok, Base DN, 저장자 BOSS, 비밀번호·암호문 없음
    assert saved.status_code == 200, saved.text
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == RESPONSE_KEYS
    assert (body["bind_credential_status"], body["base_dn"]) == ("ok", BASE_DN)
    assert body["updated_by"]["id"] == me["user_id"]
    assert NEW_BIND_PASSWORD not in response.text
    assert BIND_PASSWORD not in response.text
    assert BOSS_PASSWORD not in response.text
    assert "fake-sealed" not in response.text


async def test_reading_without_saved_settings_is_404_with_the_fixed_message() -> None:
    """AD 설정이 없으면 조회는 404 not-found와 고정 문구다.

    테스트 코드: IN-003
    """
    # given: AD 설정 행이 없다
    async with role_clients() as c:
        # when: BOSS가 AD 설정을 조회한다
        response = await c[BOSS].get(DIRECTORY)

    # then: 404 not-found, detail은 고정 문구
    body = then_problem_is(response, 404, "not-found")
    assert body["detail"] == "AD 설정을(를) 찾을 수 없습니다: directory"


async def test_a_wrong_admin_password_test_is_a_200_bind_failure_without_the_password() -> None:
    """틀린 admin 비밀번호의 연결 테스트는 200 실패 결과(bind 단계)이고 본문에 비밀번호가 없다.

    테스트 코드: IN-005
    """
    # given: 예시 AD 설정이 있다
    use_cases = await _given_saved_settings()
    async with role_clients(use_cases) as c:
        # when: BOSS가 틀린 비밀번호로 연결 테스트한다
        response = await c[BOSS].post(DIRECTORY_TEST, json=_test_body(password=WRONG_PASSWORD))

    # then: 200 success false, stage bind, 서버 문구, base_dn null
    assert response.status_code == 200, response.text
    assert response.json() == {
        "success": False,
        "stage": "bind",
        "message": STAGE_MESSAGES["bind"],
        "base_dn": None,
    }
    assert WRONG_PASSWORD not in response.text


@pytest.mark.parametrize("stage", list(FAILURES))
async def test_the_connection_test_reports_each_failed_stage_with_its_server_message(
    stage: str,
) -> None:
    """연결 테스트는 실패한 단계를 그 단계의 서버 문구로 알린다.

    테스트 코드: IN-006
    """
    # given: Fake AD가 한 단계에서 실패한다
    use_cases = await _given_saved_settings()
    where, error = FAILURES[stage]
    if where == "discover":
        use_cases.directory.discover_fails_with = error  # type: ignore[assignment]
    else:
        use_cases.directory.authenticate_fails_with = error  # type: ignore[assignment]
    async with role_clients(use_cases) as c:
        # when: BOSS가 연결 테스트한다
        response = await c[BOSS].post(DIRECTORY_TEST, json=_test_body())

    # then: 200 success false, 그 단계와 서버 문구, base_dn null
    assert response.status_code == 200, response.text
    assert response.json() == {
        "success": False,
        "stage": stage,
        "message": STAGE_MESSAGES[stage],
        "base_dn": None,
    }


@pytest.mark.parametrize("password", ["", "   ", "pw\x00x", "p" * 257])
async def test_a_malformed_admin_password_is_422_and_never_reaches_the_directory(
    password: str,
) -> None:
    """형식이 틀린 현재 admin 비밀번호는 AD를 부르지 않고 422 invalid-value다.

    테스트 코드: IN-015
    """
    # given: 예시 AD 설정이 있다
    use_cases = await _given_saved_settings()
    async with role_clients(use_cases) as c:
        # when: BOSS가 형식이 틀린 password로 저장한다
        response = await c[BOSS].put(DIRECTORY, json=_update_body(password=password))

    # then: 422 invalid-value, 비밀번호 규칙 문구, AD 호출 0회
    body = then_problem_is(response, 422, "invalid-value")
    assert "비밀번호" in body["detail"]
    assert use_cases.directory.discover_calls == []
    assert use_cases.directory.authenticate_calls == []


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"port": 0}, "port"),
        ({"bind_account": ""}, "bind_account"),
        ({"user_filter": "(uid=x)"}, "user_filter"),
        ({"connect_timeout_seconds": 31}, "connect_timeout_seconds"),
        ({"host": "ldaps://dc1"}, "host"),
    ],
)
async def test_a_malformed_connection_value_is_422_naming_the_field_and_changes_nothing(
    override: dict[str, Any], field: str
) -> None:
    """형식이 틀린 접속 정보는 필드 이름이 든 422이고 AD를 부르지 않으며 설정은 그대로다.

    테스트 코드: IN-016
    """
    # given: 예시 AD 설정(revision 1)이 있다
    use_cases = await _given_saved_settings()
    async with role_clients(use_cases) as c:
        # when: BOSS가 틀린 값 하나로 저장한다
        response = await c[BOSS].put(DIRECTORY, json=_update_body(**override))
        after = await c[BOSS].get(DIRECTORY)

    # then: 422 invalid-value, detail에 필드 이름, AD 호출 0회, 설정은 revision 1 그대로
    body = then_problem_is(response, 422, "invalid-value")
    assert field in body["detail"]
    assert use_cases.directory.discover_calls == []
    assert after.json()["revision"] == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: {**b, "base_dn": "dc=x"},
        lambda b: {**b, "server_urls": ["ldaps://x"]},
        lambda b: {**b, "bind_template": "x"},
        lambda b: {**b, "ca_pem": "x"},
        lambda b: {**b, "foo": 1},
        lambda b: {k: v for k, v in b.items() if k != "host"},
        lambda b: {k: v for k, v in b.items() if k != "expected_revision"},
        lambda b: {**b, "port": "636"},
        lambda b: {**b, "port": 636.0},
        lambda b: {**b, "port": True},
        lambda b: {**b, "security": "tls"},
        lambda b: {**b, "expected_revision": 0},
        lambda b: {**b, "expected_revision": "1"},
    ],
    ids=[
        "base_dn",
        "server_urls",
        "bind_template",
        "ca_pem",
        "unknown",
        "no-host",
        "no-revision",
        "port-str",
        "port-float",
        "port-bool",
        "security",
        "revision-0",
        "revision-str",
    ],
)
async def test_a_malformed_request_shape_is_422_request_validation_and_never_reaches_the_directory(
    mutate: Callable[[dict[str, Any]], dict[str, Any]],
) -> None:
    """폐지·모르는 필드, 필수 누락, 타입 오류는 422 request-validation이고 AD를 부르지 않는다.

    테스트 코드: IN-021
    """
    # given: 예시 AD 설정이 있다
    use_cases = await _given_saved_settings()
    async with role_clients(use_cases) as c:
        # when: BOSS가 모양이 틀린 본문으로 저장한다
        response = await c[BOSS].put(DIRECTORY, json=mutate(_update_body()))

    # then: 422 request-validation, AD 호출 0회
    then_problem_is(response, 422, "request-validation")
    assert use_cases.directory.discover_calls == []


async def test_a_connection_test_with_an_expected_revision_is_422_request_validation() -> None:
    """연결 테스트 본문에 expected_revision을 넣으면 422 request-validation이다.

    테스트 코드: IN-021
    """
    # given: 예시 AD 설정이 있다
    use_cases = await _given_saved_settings()
    async with role_clients(use_cases) as c:
        # when: BOSS가 expected_revision이 든 본문으로 연결 테스트한다
        response = await c[BOSS].post(DIRECTORY_TEST, json=_test_body(expected_revision=1))

    # then: 422 request-validation, AD 호출 0회
    then_problem_is(response, 422, "request-validation")
    assert use_cases.directory.discover_calls == []


async def test_saving_returns_the_stored_result_with_server_offset_time(
    local_tz: Callable[[str], None],
) -> None:
    """저장하면 새 설정·Base DN·저장자·서버 오프셋 시각이 나오고 이후 조회와 같다.

    테스트 코드: IN-022
    """
    # given: 예시 AD 설정(revision 1)과 서울 시간대 서버
    local_tz("Asia/Seoul")
    use_cases = await _given_saved_settings()
    async with role_clients(use_cases) as c:
        # when: BOSS가 호스트·바인드 비밀번호를 바꿔 revision 1로 저장한다
        saved = await c[BOSS].put(DIRECTORY, json=_update_body(host="dc2.corp.test"))
        read = await c[BOSS].get(DIRECTORY)
        me = (await c[BOSS].get("/api/v1/auth/me")).json()

    # then: 200, host·base_dn·revision 2·저장자 BOSS·+09:00 시각, 조회와 같음
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (body["host"], body["base_dn"], body["revision"]) == ("dc2.corp.test", BASE_DN, 2)
    assert body["updated_by"]["id"] == me["user_id"]
    assert body["updated_at"].endswith("+09:00")
    assert read.json() == body
    (call,) = use_cases.directory.authenticate_calls
    assert (call.login_id.value, call.base_dn) == ("boss", BASE_DN)


@pytest.mark.parametrize("stage", list(FAILURES))
async def test_a_failed_verification_on_save_is_422_with_the_stage_and_keeps_the_settings(
    stage: str,
) -> None:
    """확인이 단계별로 실패하면 저장은 422 directory-verification-failed와 그 단계다.

    설정은 그대로 남는다.

    테스트 코드: IN-028
    """
    # given: 예시 AD 설정(revision 1)과 한 단계에서 실패하는 Fake AD
    use_cases = await _given_saved_settings()
    where, error = FAILURES[stage]
    if where == "discover":
        use_cases.directory.discover_fails_with = error  # type: ignore[assignment]
    else:
        use_cases.directory.authenticate_fails_with = error  # type: ignore[assignment]
    async with role_clients(use_cases) as c:
        # when: BOSS가 저장한다
        response = await c[BOSS].put(DIRECTORY, json=_update_body(host="dc2.corp.test"))
        after = await c[BOSS].get(DIRECTORY)

    # then: 422, stage와 서버 문구, 설정은 revision 1·원래 호스트 그대로
    body = then_problem_is(response, 422, "directory-verification-failed")
    assert (body["stage"], body["detail"]) == (stage, STAGE_MESSAGES[stage])
    assert (after.json()["revision"], after.json()["host"]) == (1, "dc1.corp.test")


async def test_no_response_or_log_carries_the_passwords_or_the_ciphertext(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """저장·테스트·조회의 성공·오류 응답과 로그에 두 비밀번호와 암호문이 없다.

    테스트 코드: IN-034
    """
    # given: 예시 AD 설정과 로그 수집
    caplog.set_level(logging.DEBUG)
    use_cases = await _given_saved_settings()
    async with role_clients(use_cases) as c:
        # when: 저장 성공, 확인 실패 저장, 연결 테스트 성공·실패, 값 위반, 조회를 한다
        responses = [await c[BOSS].put(DIRECTORY, json=_update_body())]
        sealed = (await _stored_token(use_cases)).token
        responses.append(await c[BOSS].put(DIRECTORY, json=_update_body(password=WRONG_PASSWORD)))
        responses.append(await c[BOSS].post(DIRECTORY_TEST, json=_test_body()))
        responses.append(
            await c[BOSS].post(DIRECTORY_TEST, json=_test_body(password=WRONG_PASSWORD))
        )
        responses.append(await c[BOSS].put(DIRECTORY, json=_update_body(port=0)))
        responses.append(await c[BOSS].get(DIRECTORY))

    # then: 모든 응답 본문과 로그에 입력한 두 비밀번호와 저장된 암호문이 없다
    for response in responses:
        for secret in (NEW_BIND_PASSWORD, BOSS_PASSWORD, WRONG_PASSWORD, sealed):
            assert secret not in response.text
    logged = caplog.text
    for secret in (NEW_BIND_PASSWORD, BOSS_PASSWORD, WRONG_PASSWORD, sealed):
        assert secret not in logged


async def _stored_token(use_cases: FakeUseCases) -> SealedSecret:
    stored = await use_cases.uow.directory_settings.get()
    assert stored is not None
    return stored.sealed_bind_password


_SIX_ROUTES = [
    ("get", DIRECTORY),
    ("put", DIRECTORY),
    ("post", DIRECTORY_TEST),
    ("get", STORAGE),
    ("put", STORAGE),
    ("post", STORAGE_TEST),
]


async def test_only_admin_may_use_the_six_integration_routes() -> None:
    """연동 설정 6개 경로는 admin만 쓰고 sales·user는 본문 검사 전에 403, 미인증은 401이다.

    테스트 코드: IN-040
    """
    # given: 예시 AD 설정과 저장 위치
    use_cases = await _given_saved_settings()
    await use_cases.seed_storage("/data/a")
    async with role_clients(use_cases) as c:
        # when: 각 역할이 6개 경로를 (형식이 틀린 본문으로) 부른다
        rejected = {
            role: [
                await c[role].request(
                    method, path, json={"garbage": 1} if method != "get" else None
                )
                for method, path in _SIX_ROUTES
            ]
            for role in (KIM, VIEWER)
        }
        anonymous = [
            await c[ANONYMOUS].request(method, path, json={"x": 1} if method != "get" else None)
            for method, path in _SIX_ROUTES
        ]
        stored = await c[BOSS].get(STORAGE)

    # then: sales·user는 403 forbidden 관리자 문구, 미인증은 401, 저장 위치는 그대로
    for responses in rejected.values():
        for response in responses:
            assert then_problem_is(response, 403, "forbidden")["detail"] == ADMIN_DENIED
    for response in anonymous:
        assert then_problem_is(response, 401, "unauthenticated")["detail"] == LOGIN_REQUIRED
    assert stored.json()["path"] == "/data/a"


async def test_changes_without_the_csrf_header_are_403_and_change_nothing() -> None:
    """AD 저장·연결 테스트·저장 위치 변경은 CSRF 헤더가 없으면 403 csrf이고 아무것도 바뀌지 않는다.

    테스트 코드: IN-041
    """
    # given: 예시 AD 설정, 저장 위치, 헤더 없는 BOSS 클라이언트
    use_cases = await _given_saved_settings()
    await use_cases.seed_storage("/data/a")
    async with role_clients(use_cases, csrf=False) as c:
        # when: 헤더 없이 AD 저장, 연결 테스트, 저장 위치 변경을 부른다
        responses = [
            await c[BOSS].put(DIRECTORY, json=_update_body()),
            await c[BOSS].post(DIRECTORY_TEST, json=_test_body()),
            await c[BOSS].put(STORAGE, json={"path": "/data/b"}),
        ]
        directory = await c[BOSS].get(DIRECTORY)
        storage = await c[BOSS].get(STORAGE)

    # then: 모두 403 csrf, AD 호출 0회, 설정과 위치는 그대로
    for response in responses:
        assert then_problem_is(response, 403, "csrf")["detail"] == CSRF_DETAIL
    assert use_cases.directory.discover_calls == []
    assert (directory.json()["revision"], storage.json()["path"]) == (1, "/data/a")
