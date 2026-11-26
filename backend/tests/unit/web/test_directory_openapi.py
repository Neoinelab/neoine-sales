"""AD 설정 API의 OpenAPI 계약(IN-R21): 경로·메서드, 입력 7칸, 비밀번호 표기, 결과, 오류."""

from typing import Any

import pytest

from tests.support.openapi_spec import app_contract, operation_of

DIRECTORY = "/api/v1/settings/directory"
DIRECTORY_TEST = "/api/v1/settings/directory/test"
CONNECTION_FIELDS = {
    "host",
    "port",
    "security",
    "user_filter",
    "connect_timeout_seconds",
}


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return app_contract()


def schema_name_of(operation: dict[str, Any], *, request: bool) -> str:
    """요청 본문 또는 첫 2xx JSON 응답이 참조하는 스키마 이름."""
    if request:
        ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    else:
        ref = next(
            r["content"]["application/json"]["schema"]["$ref"]
            for code, r in operation["responses"].items()
            if code.startswith("2") and "content" in r
        )
    return str(ref).rsplit("/", 1)[-1]


def _schema(spec: dict[str, Any], method: str, path: str, *, request: bool) -> dict[str, Any]:
    name = schema_name_of(operation_of(spec, method, path), request=request)
    schema: dict[str, Any] = spec["components"]["schemas"][name]
    return schema


def _is_masked_secret(prop: dict[str, Any]) -> bool:
    candidates = [prop, *prop.get("anyOf", [])]
    return any(c.get("format") == "password" and c.get("writeOnly") is True for c in candidates)


def test_directory_settings_paths_expose_only_the_planned_methods(spec: dict[str, Any]) -> None:
    """AD 설정 경로는 GET·PUT, 연결 테스트는 POST만 공개한다.

    테스트 코드: IN-042
    """
    # when: openapi 문서를 만든다
    paths = spec["paths"]

    # then: 경로별 메서드가 계획과 같다
    assert set(paths[DIRECTORY]) == {"get", "put"}
    assert set(paths[DIRECTORY_TEST]) == {"post"}


def test_update_and_test_requests_take_the_seven_fields_the_password_and_the_revision(
    spec: dict[str, Any],
) -> None:
    """저장 요청은 7칸+password+expected_revision, 테스트 요청은 7칸+password만 받는다.

    테스트 코드: IN-042
    """
    # when: 저장·테스트 요청 스키마를 읽는다
    update = _schema(spec, "PUT", DIRECTORY, request=True)
    probe = _schema(spec, "POST", DIRECTORY_TEST, request=True)

    # then: 속성 집합, 필수 여부(expected_revision만 필수, bind_password는 필수 아님)
    assert set(update["properties"]) == CONNECTION_FIELDS | {"test_token", "expected_revision"}
    assert set(probe["properties"]) == CONNECTION_FIELDS | {"bind_account", "bind_password"}
    assert "expected_revision" in update["required"]
    assert "bind_password" not in update["required"]
    assert "bind_password" in probe["required"]


def test_bind_password_and_password_are_masked_write_only_secrets(spec: dict[str, Any]) -> None:
    """bind_password·password는 저장·테스트 요청 모두에서 format password·writeOnly다.

    테스트 코드: IN-042
    """
    # when: 두 요청 스키마의 비밀번호 속성을 읽는다
    update = _schema(spec, "PUT", DIRECTORY, request=True)
    probe = _schema(spec, "POST", DIRECTORY_TEST, request=True)
    assert _is_masked_secret(update["properties"]["test_token"])
    assert _is_masked_secret(probe["properties"]["bind_account"])
    assert _is_masked_secret(probe["properties"]["bind_password"])
    assert "bind_account" not in update["properties"]
    assert "bind_password" not in update["properties"]


def test_response_hides_the_password_and_the_result_has_four_fields(spec: dict[str, Any]) -> None:
    """응답에는 password 속성이 없고 bind_credential_status는 ok·unreadable, 결과는 4필드다.

    테스트 코드: IN-042
    """
    # when: 조회 응답과 테스트 결과 스키마를 읽는다
    response = _schema(spec, "GET", DIRECTORY, request=False)
    result = _schema(spec, "POST", DIRECTORY_TEST, request=False)

    # then: 비밀번호 속성 없음, 상태 enum, 결과 속성 4개
    assert not any("password" in key for key in response["properties"])
    assert "bind_credential_status" not in response["properties"]
    assert set(result["properties"]) == {"success", "stage", "message", "base_dn", "test_token"}


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("get", {"200", "404"}),
        ("put", {"200", "404", "409", "422", "429"}),
    ],
)
def test_documented_responses_of_the_settings_routes(
    spec: dict[str, Any], method: str, expected: set[str]
) -> None:
    """AD 설정 조회·저장이 문서화한 응답 상태가 계약과 같다.

    테스트 코드: IN-042
    """
    # when: 경로의 응답 상태를 읽는다
    documented = set(spec["paths"][DIRECTORY][method]["responses"])

    # then: 계약의 상태가 모두 문서화되어 있다
    assert expected <= documented


def test_documented_responses_of_the_connection_test(spec: dict[str, Any]) -> None:
    """연결 테스트는 200과 404·409·422·429 오류를 문서화한다.

    테스트 코드: IN-042
    """
    # when: 연결 테스트의 응답 상태를 읽는다
    documented = set(spec["paths"][DIRECTORY_TEST]["post"]["responses"])

    # then: 계약의 상태가 모두 문서화되어 있다
    assert {"200", "404", "409", "422", "429"} <= documented
