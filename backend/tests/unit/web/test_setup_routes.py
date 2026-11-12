"""최초 설정 경로의 web 판정(`/auth/setup/**`, `/auth/config` 진행 상태): FakeUseCases 위의 앱.

SU-001·004·010·014·020·025·026·033·034·040·041·042.
유스케이스 규칙은 `tests/unit/application/test_setup_*.py`다.
"""

import logging
from typing import Any

import pytest

from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories_auth import BIND_PASSWORD
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings
from tests.support.auth_seed import DUMMY_PASSWORD
from tests.unit.web.local_account_http import (
    CONFIG,
    ME,
    SETUP,
    SETUP_MODE,
    SETUP_STORAGE,
    UNUSED_DATABASE_URL,
    anonymous,
    error_locations,
    local_system,
    problem,
)

SETUP_DIRECTORY = "/api/v1/auth/setup/directory"
SETUP_STORAGE_TEST = "/api/v1/auth/setup/storage/test"
LOGIN_FAILED = "아이디 또는 비밀번호가 올바르지 않습니다"
LEAK = "internal-ldap-server-banner"


def _directory_body(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "host": "dc1.corp.test",
        "port": 636,
        "security": "ssl",
        "bind_account": "cn=svc-sales,ou=services,dc=corp,dc=test",
        "bind_password": BIND_PASSWORD,
        "user_filter": "(&(objectClass=user)(sAMAccountName={login_id}))",
        "connect_timeout_seconds": 5,
    }
    return {**values, **overrides}


async def _ad_system(use_cases: FakeUseCases) -> None:
    await use_cases.seed_directory()
    await use_cases.seed_storage()


async def test_config_of_a_new_system_is_unselected_with_directory_and_storage_needed() -> None:
    """새 시스템의 /auth/config는 방식 미선택이고 AD·저장 위치 단계가 필요하다(관리자 단계는 아직).

    테스트 코드: SU-001
    """
    # given: 사용자·방식·AD 설정·저장 위치가 하나도 없다
    async with anonymous(FakeUseCases()) as http:
        # when: 진행 상태를 조회한다
        response = await http.get(CONFIG)

    # then: 200이고 auth_mode null, directory·storage 필요, admin 아직
    body = response.json()
    assert response.status_code == 200
    assert (
        body["auth_mode"],
        body["needs_directory_setup"],
        body["needs_storage_setup"],
        body["needs_admin_setup"],
    ) == (None, True, True, False)


async def test_config_with_an_admin_and_no_setting_rows_is_all_done_and_ad() -> None:
    """재직 admin이 있으면 설정 행이 없어도 진행 상태는 모두 끝남이다.

    테스트 코드: SU-004
    """
    # given: 재직 admin이 있고 AD 설정·저장 위치 행이 없다(로그아웃 상태)
    use_cases = FakeUseCases()
    await use_cases.seed_user("boss", Role.ADMIN)
    async with anonymous(use_cases) as http:
        # when: 진행 상태를 조회한다
        body = (await http.get(CONFIG)).json()

    # then: 셋 다 false, auth_mode ad, directory_login false
    assert (
        body["needs_directory_setup"],
        body["needs_storage_setup"],
        body["needs_admin_setup"],
    ) == (False, False, False)
    assert (body["auth_mode"], body["directory_login"]) == ("ad", False)


@pytest.mark.parametrize(
    "body",
    [{"mode": "oidc"}, {"mode": "AD"}, {}, {"mode": "local", "x": 1}],
    ids=["unknown", "uppercase", "missing", "extra-field"],
)
async def test_an_unknown_auth_mode_is_a_request_validation_error(body: dict[str, Any]) -> None:
    """알 수 없는 인증 방식은 422 request-validation이다.

    테스트 코드: SU-010
    """
    # given: 새 시스템이다
    async with anonymous(FakeUseCases()) as http:
        # when: 잘못된 본문으로 방식을 고른다
        response = await http.put(SETUP_MODE, json=body)
        config = (await http.get(CONFIG)).json()

    # then: 422 request-validation이고 방식은 바뀌지 않는다
    problem(response, 422, "request-validation")
    assert config["auth_mode"] is None


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
    ],
)
async def test_a_malformed_directory_body_is_rejected_without_calling_the_directory(
    override: dict[str, object], kind: str
) -> None:
    """형식이 틀린 AD 서버 입력은 422이고 AD를 부르지 않는다.

    테스트 코드: SU-014
    """
    # given: 새 시스템이다
    use_cases = FakeUseCases()
    body = _directory_body(**override)
    async with anonymous(use_cases) as http:
        # when: 칸 하나가 틀린 본문으로 AD 서버를 등록한다
        response = await http.put(SETUP_DIRECTORY, json=body)
        config = (await http.get(CONFIG)).json()

    # then: 칸 값 위반은 invalid-value, 형식 위반은 request-validation, AD 확인 0회, 상태 그대로
    problem(response, 422, kind)
    assert use_cases.directory.discover_calls == []
    assert config["needs_directory_setup"] is True


async def test_a_missing_bind_password_is_a_request_validation_error() -> None:
    """바인드 비밀번호 누락은 request-validation이고 AD를 부르지 않는다.

    테스트 코드: SU-014
    """
    # given: 새 시스템이다
    use_cases = FakeUseCases()
    body = _directory_body()
    del body["bind_password"]
    async with anonymous(use_cases) as http:
        # when: bind_password 없이 AD 서버를 등록한다
        response = await http.put(SETUP_DIRECTORY, json=body)

    # then: 422 request-validation, AD 확인 0회
    problem(response, 422, "request-validation")
    assert use_cases.directory.discover_calls == []


@pytest.mark.parametrize(
    "body",
    [{}, {"path": 1}, {"path": "/x", "extra": 1}],
    ids=["missing", "not-a-string", "extra-field"],
)
async def test_a_malformed_storage_body_is_a_request_validation_error(
    body: dict[str, Any],
) -> None:
    """저장 위치 본문 형식이 틀리면 422 request-validation이다.

    테스트 코드: SU-020
    """
    # given: 저장 위치를 등록할 수 있는 local 시스템이다
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.LOCAL)
    async with anonymous(use_cases) as http:
        # when: 형식이 틀린 본문으로 저장 위치를 등록한다
        response = await http.put(SETUP_STORAGE, json=body)
        config = (await http.get(CONFIG)).json()

    # then: 422 request-validation이고 저장값은 없다
    problem(response, 422, "request-validation")
    assert config["needs_storage_setup"] is True


@pytest.mark.parametrize("password", ["", "   ", "pw\u0000x"], ids=["empty", "blank", "nul"])
async def test_a_blank_or_nul_password_in_ad_mode_is_401_and_never_reaches_the_directory(
    password: str,
) -> None:
    """AD 방식의 빈 비밀번호는 AD에 보내지 않고 401이다.

    테스트 코드: SU-025
    """
    # given: AD 서버·저장 위치가 등록되었다
    use_cases = FakeUseCases()
    await _ad_system(use_cases)
    async with anonymous(use_cases) as http:
        # when: 비어 있거나 NUL이 든 비밀번호로 첫 admin을 등록한다
        response = await http.post(SETUP, json={"login_id": "kim", "password": password})

    # then: 로그인 실패 문구의 401이고 AD 호출은 0회다
    assert problem(response, 401, "unauthenticated")["detail"] == LOGIN_FAILED
    assert use_cases.directory.authenticate_calls == []


async def test_a_directory_outage_is_a_503_without_the_cause() -> None:
    """AD 장애는 원인 문구 없는 503이고 사용자는 등록되지 않는다.

    테스트 코드: SU-026
    """
    # given: AD 서버·저장 위치가 등록되었고 AD 인증이 TLS 단계 장애(원인 문구 포함)로 실패한다
    use_cases = FakeUseCases()
    await _ad_system(use_cases)
    use_cases.directory.add_account("kim", "pw-kim")
    use_cases.directory.authenticate_fails_with = DirectoryUnavailableError(
        LEAK, stage=VerificationStage.TLS
    )
    async with anonymous(use_cases) as http:
        # when: 첫 admin을 등록한다
        response = await http.post(SETUP, json={"login_id": "kim", "password": "pw-kim"})
        config = (await http.get(CONFIG)).json()

    # then: 503 directory-unavailable 고정 문구이고 원인 문구가 없으며 admin 단계는 그대로다
    body = problem(response, 503, "directory-unavailable")
    assert body["detail"] == "인증 서버(AD)에 연결할 수 없습니다. 잠시 후 다시 시도하세요"
    assert LEAK not in response.text
    assert config["needs_admin_setup"] is True


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("short7!", "비밀번호는 8자 이상이어야 합니다"),
        ("  BOSS  ", "비밀번호는 아이디와 같을 수 없습니다"),
    ],
)
async def test_a_weak_local_password_is_422_on_the_password_field(
    password: str, message: str
) -> None:
    """local 비밀번호가 8자 미만이거나 아이디와 같으면 password 칸 422이다.

    테스트 코드: SU-033
    """
    # given: 방식 local, 저장 위치가 등록되었다
    use_cases = FakeUseCases()
    await local_system(use_cases)
    async with anonymous(use_cases) as http:
        # when: 아이디 boss에 약한 비밀번호로 등록한다
        response = await http.post(
            SETUP, json={"login_id": "boss", "password": password, "display_name": "보스"}
        )
        config = (await http.get(CONFIG)).json()

    # then: invalid-value, errors는 password 칸, 설정은 열린 채다
    body = problem(response, 422, "invalid-value")
    assert body["detail"] == message
    assert error_locations(body) == [["password"]]
    assert config["needs_admin_setup"] is True


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("", "비밀번호는 비어 있을 수 없습니다"),
        ("   ", "비밀번호는 비어 있을 수 없습니다"),
        ("pw\u0000xxxxxx", "비밀번호에는 NUL 문자를 쓸 수 없습니다"),
    ],
    ids=["empty", "blank", "nul"],
)
async def test_a_blank_or_nul_local_password_is_422_on_the_password_field_not_401(
    password: str, message: str
) -> None:
    """local 방식의 빈·공백·NUL 비밀번호는 401이 아니라 password 칸 422다.

    테스트 코드: SU-034
    """
    # given: 방식 local, 저장 위치가 등록되었다
    use_cases = FakeUseCases()
    await local_system(use_cases)
    async with anonymous(use_cases) as http:
        # when: 빈·공백·NUL 비밀번호로 등록한다
        response = await http.post(
            SETUP, json={"login_id": "boss", "password": password, "display_name": "보스"}
        )

    # then: 422 invalid-value, errors[0].location은 password, 해당 문구다
    body = problem(response, 422, "invalid-value")
    assert error_locations(body)[0] == ["password"]
    assert body["errors"][0]["message"] == message  # type: ignore[index]


async def test_the_setup_routes_work_without_a_session() -> None:
    """최초 설정 경로는 로그인 없이 쓸 수 있고 호출 뒤에도 호출자는 익명이다.

    테스트 코드: SU-040
    """
    # given: 로그인하지 않았다(세션 쿠키 없음)
    use_cases = FakeUseCases()
    async with anonymous(use_cases) as http:
        # when: AD 서버 등록, 저장 위치 등록을 부른다
        directory = await http.put(SETUP_DIRECTORY, json=_directory_body())
        storage = await http.put(SETUP_STORAGE, json={"path": "/data/neoine/files"})
        me = await http.get(ME)

    # then: 각각 200이고 요청 뒤에도 익명이다(/auth/me 401)
    assert (directory.status_code, storage.status_code) == (200, 200)
    assert me.status_code == 401


async def test_neither_password_appears_in_any_response_or_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """첫 admin·바인드 비밀번호는 응답과 로그 어디에도 나오지 않는다.

    테스트 코드: SU-041
    """
    # given: 로그를 DEBUG까지 모으고 새 시스템에서 AD 서버를 등록하려 한다
    caplog.set_level(logging.DEBUG)
    use_cases = FakeUseCases()
    use_cases.directory.add_account("kim", DUMMY_PASSWORD)
    responses = []
    async with anonymous(use_cases) as http:
        # when: 바인드 비밀번호로 AD 서버 등록(성공·확인 실패)을 보낸다
        responses.append(await http.put(SETUP_DIRECTORY, json=_directory_body()))
        use_cases.directory.discover_fails_with = DirectoryUnavailableError(
            LEAK, stage=VerificationStage.CONNECT
        )
        responses.append(await http.put(SETUP_DIRECTORY, json=_directory_body()))
        use_cases.directory.discover_fails_with = None
        await use_cases.seed_storage()
        # when: 같은 비밀번호로 첫 admin 등록을 오답(401)·검증 오류(422)·성공(200)으로 보낸다
        wrong = await http.post(SETUP, json={"login_id": "ghost", "password": DUMMY_PASSWORD})
        invalid = await http.post(
            SETUP,
            json={"login_id": "kim", "password": DUMMY_PASSWORD, "display_name": "x"},
        )
        ok = await http.post(SETUP, json={"login_id": "kim", "password": DUMMY_PASSWORD})

    # then: 상태 코드는 401·422·200이고 어느 응답 본문과 로그에도 두 비밀번호가 없다
    assert [wrong.status_code, invalid.status_code, ok.status_code] == [401, 422, 200]
    assert [r.status_code for r in responses] == [200, 422]
    everything = " ".join(r.text for r in (*responses, wrong, invalid, ok)) + caplog.text
    assert DUMMY_PASSWORD not in everything
    assert BIND_PASSWORD not in everything


def test_openapi_documents_the_five_setup_routes_and_their_request_shapes() -> None:
    """openapi에 최초 설정 경로와 요청 모양이 문서화된다.

    테스트 코드: SU-042
    """
    # when: 앱의 openapi 문서를 만든다
    schema = create_app(
        settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases()
    ).openapi()
    paths = schema["paths"]
    schemas = schema["components"]["schemas"]

    # then: 다섯 경로·메서드가 있다
    assert set(paths["/api/v1/auth/setup/auth-mode"]) == {"put"}
    assert set(paths["/api/v1/auth/setup/directory"]) == {"put"}
    assert set(paths["/api/v1/auth/setup/storage"]) == {"put"}
    assert set(paths["/api/v1/auth/setup/storage/test"]) == {"post"}
    assert set(paths["/api/v1/auth/setup"]) == {"post"}
    # then: AuthModeRequest는 mode 하나(ad·local)
    assert set(schemas["AuthModeRequest"]["properties"]) == {"mode"}
    assert schemas["AuthMode"]["enum"] == ["ad", "local"]
    # then: SetupAdminRequest의 프로필 필드는 선택이다
    required = set(schemas["SetupAdminRequest"]["required"])
    assert required == {"login_id", "password"}
    assert {"display_name", "email", "phone"} <= set(schemas["SetupAdminRequest"]["properties"])
    # then: 저장 위치 두 경로의 응답 코드는 409·422를 포함한다
    for method, path in (
        ("put", "/api/v1/auth/setup/storage"),
        ("post", "/api/v1/auth/setup/storage/test"),
    ):
        assert {"409", "422"} <= set(paths[path][method]["responses"])


def test_openapi_setup_directory_request_takes_the_seven_fields_with_a_masked_password() -> None:
    """최초 설정 AD 요청은 연결 7칸만 받고 바인드 비밀번호는 필수·마스킹되는 쓰기 전용 값이다.

    테스트 코드: SU-042
    """
    # when: 앱의 openapi 문서에서 최초 설정 AD 요청 스키마를 읽는다
    spec = create_app(
        settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases()
    ).openapi()
    operation = spec["paths"]["/api/v1/auth/setup/directory"]["put"]
    ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema = spec["components"]["schemas"][str(ref).rsplit("/", 1)[-1]]

    # then: 속성은 7칸뿐이고 bind_password는 필수이며 마스킹되는 쓰기 전용이다
    assert set(schema["properties"]) == {
        "host",
        "port",
        "security",
        "bind_account",
        "bind_password",
        "user_filter",
        "connect_timeout_seconds",
    }
    assert "bind_password" in schema["required"]
    prop = schema["properties"]["bind_password"]
    assert any(
        c.get("format") == "password" and c.get("writeOnly") is True
        for c in [prop, *prop.get("anyOf", [])]
    )
