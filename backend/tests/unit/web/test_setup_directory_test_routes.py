"""최초 설정 AD 연결 테스트 경로(`POST /auth/setup/directory/test`)의 web 판정: SU-065~SU-071.

유스케이스 규칙은 `tests/unit/application/test_setup_directory_test_cases.py`다.
"""

import logging

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories_auth import BIND_PASSWORD
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings
from tests.unit.web.local_account_http import (
    CONFIG,
    ME,
    UNUSED_DATABASE_URL,
    anonymous,
    problem,
)
from tests.unit.web.test_setup_routes import SETUP_DIRECTORY, _directory_body

TEST_DIRECTORY = "/api/v1/auth/setup/directory/test"
LEAK = "internal-ldap-detail"
SUCCESS_MESSAGE = "AD 설정을 확인했습니다"
STAGE_TEXT = {
    "connect": "AD 서버에 연결하지 못했습니다. 호스트·포트·방화벽을 확인하세요",
    "tls": "TLS 연결에 실패했습니다. 보안 연결(SSL/StartTLS) 방식과 포트를 확인하세요",
    "service_bind": "바인드 계정으로 AD에 로그인하지 못했습니다. 계정과 비밀번호를 확인하세요",
    "base_dn": (
        "AD에서 Base DN(defaultNamingContext)을 찾지 못했습니다. 바인드 계정 권한을 확인하세요"
    ),
}


async def test_a_successful_test_is_200_with_the_base_dn_and_stores_nothing() -> None:
    """연결 테스트가 성공하면 200 성공 결과와 Base DN을 돌려주고 저장하지 않는다.

    테스트 코드: SU-065
    """
    # given: 새 시스템이고 AD가 Base DN dc=found,dc=test를 알려 준다
    use_cases = FakeUseCases()
    use_cases.directory.base_dn = "dc=found,dc=test"
    async with anonymous(use_cases) as http:
        # when: 입력 7칸으로 AD 연결 테스트를 한다
        response = await http.post(TEST_DIRECTORY, json=_directory_body())
        config = (await http.get(CONFIG)).json()

    # then: 200 성공 결과
    assert response.status_code == 200, response.text
    assert response.json() == {
        "success": True,
        "stage": None,
        "message": SUCCESS_MESSAGE,
        "base_dn": "dc=found,dc=test",
        "test_token": response.json()["test_token"],
    }
    # then: Base DN 탐색만 1회, 사용자 인증 없음, 진행 상태는 그대로
    assert len(use_cases.directory.discover_calls) == 1
    assert use_cases.directory.authenticate_calls == []
    assert (
        config["auth_mode"],
        config["needs_directory_setup"],
        config["needs_storage_setup"],
    ) == (
        None,
        True,
        True,
    )


@pytest.mark.parametrize(
    ("stage", "no_stage"),
    [
        ("connect", False),
        ("tls", False),
        ("service_bind", False),
        ("base_dn", False),
        ("connect", True),
    ],
    ids=["connect", "tls", "service_bind", "base_dn", "no-stage"],
)
async def test_a_failed_check_is_200_with_the_stage_message_and_no_leak(
    stage: str, *, no_stage: bool
) -> None:
    """확인이 실패해도 200이고 단계·서버 문구만 담으며 원인 문구는 없다.

    테스트 코드: SU-066
    """
    # given: AD 확인이 원인 문구와 함께 그 단계(또는 단계 정보 없이)에서 실패한다
    use_cases = FakeUseCases()
    use_cases.directory.discover_fails_with = DirectoryUnavailableError(
        LEAK, stage=None if no_stage else VerificationStage(stage)
    )
    async with anonymous(use_cases) as http:
        # when: AD 연결 테스트를 한다
        response = await http.post(TEST_DIRECTORY, json=_directory_body())
        config = (await http.get(CONFIG)).json()

    # then: 200 success false, 단계, 단계 문구, base_dn null
    assert response.status_code == 200, response.text
    assert response.json() == {
        "success": False,
        "stage": stage,
        "message": STAGE_TEXT[stage],
        "base_dn": None,
        "test_token": None,
    }
    # then: 원인 문구·바인드 비밀번호가 응답에 없고 저장되지 않았다
    assert LEAK not in response.text
    assert BIND_PASSWORD not in response.text
    assert config["needs_directory_setup"] is True


@pytest.mark.parametrize("chose_local", [False, True], ids=["ad-registered", "local-chosen"])
async def test_a_stored_directory_or_chosen_mode_is_left_as_it_was(*, chose_local: bool) -> None:
    """저장된 AD 설정이나 고른 방식이 있어도 테스트는 입력값만 쓰고 상태를 바꾸지 않는다.

    테스트 코드: SU-067
    """
    # given: (가) AD 서버가 등록되어 있다 / (나) 방식 local을 골랐다
    use_cases = FakeUseCases()
    if chose_local:
        await use_cases.seed_auth_mode(AuthMode.LOCAL)
    else:
        await use_cases.seed_auth_mode(AuthMode.AD)
        await use_cases.seed_directory()
    async with anonymous(use_cases) as http:
        before = (await http.get(CONFIG)).json()
        # when: 호스트 dc2.corp.test와 새 바인드 비밀번호로 연결 테스트를 한다
        response = await http.post(
            TEST_DIRECTORY,
            json=_directory_body(host="dc2.corp.test", bind_password="new-pw-1"),  # noqa: S106
        )
        after = (await http.get(CONFIG)).json()

    # then: 200 성공이고 AD는 입력한 호스트로 확인되었으며 진행 상태·방식이 그대로다
    assert (response.status_code, response.json()["success"]) == (200, True)
    assert use_cases.directory.discover_calls[-1].connection.host == "dc2.corp.test"
    assert after == before
    assert after["auth_mode"] == ("local" if chose_local else "ad")


@pytest.mark.parametrize(
    ("override", "kind"),
    [
        ({"host": ""}, "invalid-value"),
        ({"port": 0}, "invalid-value"),
        ({"port": "636"}, "request-validation"),
        ({"security": "tls"}, "request-validation"),
        ({"bind_password": ""}, "invalid-value"),
        ({"bind_password": "pw\u0000x"}, "invalid-value"),
        ({"bind_password": None}, "request-validation"),
        ({"server_urls": ["ldap://dc1"]}, "request-validation"),
        ({"password": "current-admin-pw"}, "request-validation"),
        ({"expected_revision": 1}, "request-validation"),
    ],
    ids=[
        "host-empty",
        "port-zero",
        "port-string",
        "security-enum",
        "password-empty",
        "password-nul",
        "password-null",
        "old-field",
        "admin-password",
        "expected-revision",
    ],
)
async def test_a_malformed_test_body_is_422_without_calling_the_directory(
    override: dict[str, object], kind: str
) -> None:
    """형식이 틀린 연결 테스트 입력은 422이고 AD를 부르지 않는다.

    테스트 코드: SU-068
    """
    # given: 새 시스템이다
    use_cases = FakeUseCases()
    async with anonymous(use_cases) as http:
        # when: 칸 하나가 틀린(또는 모르는 필드가 든) 본문으로 연결 테스트를 한다
        response = await http.post(TEST_DIRECTORY, json=_directory_body(**override))

    # then: 칸 값 위반은 invalid-value, 형식 위반은 request-validation, AD 확인 0회
    problem(response, 422, kind)
    assert use_cases.directory.discover_calls == []


async def test_a_missing_bind_password_is_a_request_validation_error_for_the_test() -> None:
    """바인드 비밀번호 누락은 request-validation이고 AD를 부르지 않는다.

    테스트 코드: SU-068
    """
    # given: 새 시스템이다
    use_cases = FakeUseCases()
    body = _directory_body()
    del body["bind_password"]
    async with anonymous(use_cases) as http:
        # when: bind_password 없이 연결 테스트를 한다
        response = await http.post(TEST_DIRECTORY, json=body)

    # then: 422 request-validation, AD 확인 0회
    problem(response, 422, "request-validation")
    assert use_cases.directory.discover_calls == []


async def test_a_malformed_body_is_422_even_when_setup_is_closed() -> None:
    """판정 순서는 형식이 먼저라 닫혀 있어도 형식 위반은 422다.

    테스트 코드: SU-068
    """
    # given: 재직 admin이 있어 설정이 닫혀 있다
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    await use_cases.seed_user("boss", Role.ADMIN)
    async with anonymous(use_cases) as http:
        # when: 형식이 틀린 본문으로 연결 테스트를 한다
        response = await http.post(TEST_DIRECTORY, json=_directory_body(host=""))

    # then: 409가 아니라 422이고 AD 확인은 0회다
    problem(response, 422, "invalid-value")
    assert use_cases.directory.discover_calls == []


async def test_a_closed_setup_is_409_and_the_directory_is_not_called() -> None:
    """설정이 닫혔으면 연결 테스트는 409이고 AD를 부르지 않는다.

    테스트 코드: SU-069
    """
    # given: 재직 admin이 있고 로그아웃 상태다
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.AD)
    await use_cases.seed_user("boss", Role.ADMIN)
    async with anonymous(use_cases) as http:
        # when: 올바른 입력으로 연결 테스트를 한다
        response = await http.post(TEST_DIRECTORY, json=_directory_body())

    # then: 409 invalid-state와 닫힘 문구, AD 확인 호출 없음
    body = problem(response, 409, "invalid-state")
    assert body["detail"] == "이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다"
    assert use_cases.directory.discover_calls == []


async def test_the_test_route_works_without_a_session_and_requires_the_csrf_header() -> None:
    """연결 테스트는 로그인 없이 되고 호출자는 익명으로 남으며 CSRF 헤더가 없으면 403이다.

    테스트 코드: SU-070
    """
    # given: 로그인하지 않았다(세션 쿠키 없음)
    use_cases = FakeUseCases()
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    async with anonymous(use_cases) as http:
        # when: 연결 테스트를 보내고, 헤더 없는 클라이언트로도 보낸다
        ok = await http.post(TEST_DIRECTORY, json=_directory_body())
        me = await http.get(ME)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as bare:
        no_csrf = await bare.post(TEST_DIRECTORY, json=_directory_body())

    # then: 200이고 요청 뒤에도 익명(401), 헤더가 없으면 403 csrf
    assert ok.status_code == 200
    assert me.status_code == 401
    problem(no_csrf, 403, "csrf")


async def test_the_bind_password_never_appears_in_a_response_or_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """연결 테스트의 바인드 비밀번호는 성공·실패 응답과 로그 어디에도 나오지 않는다.

    테스트 코드: SU-070
    """
    # given: 로그를 DEBUG까지 모은다
    caplog.set_level(logging.DEBUG)
    use_cases = FakeUseCases()
    async with anonymous(use_cases) as http:
        # when: 성공과 확인 실패를 각각 보낸다
        ok = await http.post(TEST_DIRECTORY, json=_directory_body())
        use_cases.directory.discover_fails_with = DirectoryUnavailableError(
            LEAK, stage=VerificationStage.SERVICE_BIND
        )
        failed = await http.post(TEST_DIRECTORY, json=_directory_body())
        registered = await http.put(SETUP_DIRECTORY, json=_directory_body())

    # then: 둘 다 200이고 응답 본문과 로그에 비밀번호·원인 문구가 없다
    assert (ok.status_code, failed.status_code) == (200, 200)
    assert registered.status_code == 422  # 같은 입력의 등록은 확인 실패를 오류로 낸다(SU-R6)
    everything = ok.text + failed.text + caplog.text
    assert BIND_PASSWORD not in everything
    assert LEAK not in ok.text + failed.text


def test_openapi_documents_the_directory_test_route_and_its_shapes() -> None:
    """openapi에 연결 테스트 경로와 요청·응답 모양이 문서화된다.

    테스트 코드: SU-071
    """
    # when: 앱의 openapi 문서를 만든다
    spec = create_app(
        settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases()
    ).openapi()
    path = spec["paths"]["/api/v1/auth/setup/directory/test"]
    schemas = spec["components"]["schemas"]

    # then: post만 있고 요청은 DirectorySettingsRequest(PUT과 같은 7칸)다
    assert set(path) == {"post"}
    request = path["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert str(request["$ref"]).endswith("/DirectorySettingsRequest")
    body = schemas["DirectorySettingsRequest"]
    assert "bind_password" in body["required"]
    assert body["properties"]["bind_password"]["writeOnly"] is True
    assert body["properties"]["bind_password"]["format"] == "password"
    # then: 200 응답은 DirectoryTestResultResponse(4필드), 문서화된 오류는 409·422
    ok = path["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert str(ok["$ref"]).endswith("/DirectoryTestResultResponse")
    assert set(schemas["DirectoryTestResultResponse"]["properties"]) == {
        "success",
        "stage",
        "message",
        "base_dn",
        "test_token",
    }
    assert {"409", "422"} <= set(path["post"]["responses"])
