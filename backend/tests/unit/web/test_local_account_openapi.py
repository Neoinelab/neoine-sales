"""앱 자체 계정 관리 API의 OpenAPI 계약: 경로·메서드·응답 코드·스키마.

커밋된 openapi.json과의 일치(드리프트)는
PL-034(`test_openapi_contract.py`)가 검사한다. 이 파일은 핵심을 직접
고정해 스키마가 갱신되지 않았거나 필드가 빠진 경우를 구체적으로 드러낸다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


def _schema(spec: dict[str, Any], name: str) -> dict[str, Any]:
    schema: dict[str, Any] = spec["components"]["schemas"][name]
    return schema


def _request_schema_name(spec: dict[str, Any], method: str, path: str) -> str:
    ref = spec["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"][
        "$ref"
    ]
    return str(ref).rsplit("/", 1)[-1]


def _response_codes(spec: dict[str, Any], method: str, path: str) -> set[str]:
    return set(spec["paths"][path][method]["responses"])


def test_new_paths_and_methods(spec: dict[str, Any]) -> None:
    """내 정보 경로는 지정한 메서드만 문서화한다(me/profile get·patch, me/password put).

    테스트 코드: ME-031
    """
    # when: 경로별 메서드를 읽는다 (전제: 앱의 openapi 문서(spec))
    paths = spec["paths"]

    # then: 내 정보 경로의 메서드가 문서와 같다(다른 feature 경로는 각 feature가 소유)
    assert set(paths["/api/v1/auth/setup/auth-mode"]) == {"put"}
    assert set(paths["/api/v1/users/{user_id}"]) == {"delete", "patch"}
    assert set(paths["/api/v1/users/{user_id}/password"]) == {"put"}
    assert set(paths["/api/v1/me/profile"]) == {"get", "patch"}
    assert set(paths["/api/v1/me/password"]) == {"put"}


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("put", "/api/v1/auth/setup/auth-mode", {"204", "409", "422"}),
        ("patch", "/api/v1/users/{user_id}", {"200", "401", "403", "404", "409", "422"}),
        ("put", "/api/v1/users/{user_id}/password", {"204", "401", "403", "404", "409", "422"}),
        ("get", "/api/v1/me/profile", {"200", "401"}),
        ("patch", "/api/v1/me/profile", {"200", "401", "409", "422"}),
        ("put", "/api/v1/me/password", {"204", "401", "409", "422", "429"}),
        ("put", "/api/v1/settings/directory", {"409"}),
        ("post", "/api/v1/settings/directory/test", {"409"}),
    ],
)
def test_documented_success_and_problem_responses(
    spec: dict[str, Any], method: str, path: str, expected: set[str]
) -> None:
    """내 정보 경로의 성공·오류 응답 코드가 문서화된다(다른 feature 경로 행은 해당 feature 소유).

    테스트 코드: ME-031
    """
    # when: 경로·메서드의 응답 코드를 읽는다 (전제: 앱의 openapi 문서)
    actual = _response_codes(spec, method, path)
    # then: 기대 코드가 모두 문서화되어 있다
    assert expected <= actual


def test_the_no_content_responses_have_no_body(spec: dict[str, Any]) -> None:
    """PUT /me/password의 204 응답에는 본문(content)이 없다.

    테스트 코드: ME-031
    """
    # when·then: 204 응답에 content가 없다 (전제: 앱의 openapi 문서)
    for method, path in (
        ("put", "/api/v1/auth/setup/auth-mode"),
        ("put", "/api/v1/users/{user_id}/password"),
        ("put", "/api/v1/me/password"),
    ):
        assert "content" not in spec["paths"][path][method]["responses"]["204"]


def test_auth_config_has_exactly_the_setup_keys_without_dev_login(spec: dict[str, Any]) -> None:
    """AuthConfigResponse는 설정 키만 가지며 dev_login이 없다."""
    # when: AuthConfigResponse 스키마를 읽는다
    schema = _schema(spec, "AuthConfigResponse")

    # then: 속성이 설정 키 다섯 개뿐이고 auth_mode는 필수·nullable이다
    assert set(schema["properties"]) == {
        "directory_login",
        "needs_directory_setup",
        "needs_storage_setup",
        "needs_admin_setup",
        "auth_mode",
    }
    assert "auth_mode" in schema["required"]
    options = schema["properties"]["auth_mode"]["anyOf"]
    assert {"type": "null"} in options


def test_the_dev_login_path_and_schema_are_gone(spec: dict[str, Any]) -> None:
    """개발용 로그인 경로와 스키마는 openapi에 없다."""
    # when: openapi 문서를 확인한다
    actual = spec["paths"]
    # then: dev-login 경로·요청 스키마·dev_login 속성이 없다
    assert "/api/v1/auth/dev-login" not in actual
    assert "DevLoginRequest" not in spec["components"]["schemas"]
    assert "dev_login" not in _schema(spec, "AuthConfigResponse")["properties"]


def test_user_response_has_a_nullable_phone(spec: dict[str, Any]) -> None:
    """UserResponse에는 필수이면서 null 가능한 phone이 있다."""
    # when: UserResponse 스키마를 읽는다
    schema = _schema(spec, "UserResponse")

    # then: phone이 속성·필수이고 null을 허용한다
    assert "phone" in schema["properties"]
    assert "phone" in schema["required"]
    assert {"type": "null"} in schema["properties"]["phone"]["anyOf"]


def test_user_request_has_optional_profile_fields_and_a_secret_password(
    spec: dict[str, Any],
) -> None:
    """UserRequest는 선택 프로필 필드와 비밀 password를 가진다."""
    # when: UserRequest 스키마를 읽는다
    schema = _schema(spec, "UserRequest")

    # then: 필수는 login_id·role뿐이고 password는 쓰기 전용 비밀이다
    assert {"login_id", "role", "display_name", "email", "phone", "password"} == set(
        schema["properties"]
    )
    assert set(schema["required"]) == {"login_id", "role"}
    password = next(
        option
        for option in schema["properties"]["password"]["anyOf"]
        if option.get("type") == "string"
    )
    assert (password.get("format"), password.get("writeOnly")) == ("password", True)


def test_the_profile_patch_requests_take_only_the_three_fields(spec: dict[str, Any]) -> None:
    """PATCH /me/profile 요청 스키마는 display_name·email·phone만 받고 required가 없다.

    테스트 코드: ME-031
    """
    # when·then: 속성 세 개뿐, required 없음, 알 수 없는 키 금지다 (전제: openapi 문서)
    for method, path in (("patch", "/api/v1/users/{user_id}"), ("patch", "/api/v1/me/profile")):
        schema = _schema(spec, _request_schema_name(spec, method, path))
        assert set(schema["properties"]) == {"display_name", "email", "phone"}
        assert not schema.get("required")
        assert schema.get("additionalProperties") is False


def test_password_requests_are_masked_write_only_secrets(spec: dict[str, Any]) -> None:
    """비밀번호 필드는 format password·writeOnly·maxLength 256으로 표기된다.

    테스트 코드: ME-031
    """
    # when·then: 비밀번호 필드가 마스킹된 쓰기 전용 비밀이다 (전제: openapi 문서)
    cases = (
        ("put", "/api/v1/users/{user_id}/password", ("password",)),
        ("put", "/api/v1/me/password", ("current_password", "new_password")),
        ("post", "/api/v1/auth/setup", ("password",)),
        ("post", "/api/v1/auth/login", ("password",)),
    )
    for method, path, fields in cases:
        schema = _schema(spec, _request_schema_name(spec, method, path))
        assert set(fields) <= set(schema["properties"])
        for field in fields:
            prop = schema["properties"][field]
            assert (prop.get("format"), prop.get("writeOnly")) == ("password", True), (path, field)
            assert prop.get("maxLength") == 256


def test_my_profile_response_shape(spec: dict[str, Any]) -> None:
    """내 정보 응답은 id integer, editable 네 속성은 boolean·required다.

    테스트 코드: ME-031
    """
    # given: 앱의 openapi 문서
    name = spec["paths"]["/api/v1/me/profile"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].rsplit("/", 1)[-1]
    # when: GET /me/profile 200 응답 스키마를 읽는다
    schema = _schema(spec, name)

    # then: 속성 8개, id는 integer, editable 네 속성은 boolean이고 모두 required다
    assert set(schema["properties"]) == {
        "id",
        "login_id",
        "role",
        "display_name",
        "email",
        "phone",
        "auth_mode",
        "editable",
    }
    assert schema["properties"]["id"]["type"] == "integer"
    editable_ref = schema["properties"]["editable"]["$ref"].rsplit("/", 1)[-1]
    editable = _schema(spec, editable_ref)
    assert set(editable["properties"]) == {"display_name", "email", "phone", "password"}
    assert all(p["type"] == "boolean" for p in editable["properties"].values())
    assert set(editable["required"]) == {"display_name", "email", "phone", "password"}


def test_both_profile_endpoints_return_the_same_response_schema(spec: dict[str, Any]) -> None:
    """GET·PATCH /me/profile의 200 응답은 같은 스키마를 가리킨다.

    테스트 코드: ME-031
    """

    # when·then: 두 200 응답의 $ref가 같다 (전제: 앱의 openapi 문서)
    def name(method: str) -> str:
        ref = spec["paths"]["/api/v1/me/profile"][method]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        return str(ref)

    assert name("get") == name("patch")
