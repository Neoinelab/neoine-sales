"""저장 위치 API의 OpenAPI 계약: 경로·메서드·응답 코드·스키마.

커밋된 openapi.json과의 일치(드리프트)는
PL-034(`test_openapi_contract.py`)가 검사한다. 이 파일은 새 계약의 핵심을
직접 고정해, 스키마가 갱신되지 않았거나 필드가 빠진 경우를 구체적으로 드러낸다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


def _responses(schema: dict[str, Any], method: str, path: str) -> set[str]:
    return set(schema["paths"][path][method]["responses"])


def test_storage_settings_paths_and_methods(schema: dict[str, Any]) -> None:
    """저장 위치 경로는 GET·PUT, 쓰기 테스트는 POST만 공개한다.

    테스트 코드: IN-058
    """
    # when: openapi 문서의 경로를 읽는다
    paths = schema["paths"]

    # then: 메서드가 계획과 같다
    assert set(paths["/api/v1/settings/storage"]) == {"get", "put"}
    assert set(paths["/api/v1/settings/storage/test"]) == {"post"}
    assert set(paths["/api/v1/auth/setup/storage"]) == {"put"}
    assert set(paths["/api/v1/auth/setup/storage/test"]) == {"post"}


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("get", "/api/v1/settings/storage", {"200", "404"}),
        ("put", "/api/v1/settings/storage", {"200", "422"}),
        ("post", "/api/v1/settings/storage/test", {"204", "422"}),
        ("put", "/api/v1/auth/setup/storage", {"200", "409", "422"}),
        ("post", "/api/v1/auth/setup/storage/test", {"204", "409", "422"}),
    ],
)
def test_documented_success_and_problem_responses(
    schema: dict[str, Any], method: str, path: str, expected: set[str]
) -> None:
    """저장 위치 경로의 성공·오류 응답 상태가 문서화되어 있다.

    테스트 코드: IN-058
    """
    # when: 경로별 응답 상태를 읽는다
    actual = _responses(schema, method, path)
    # then: 계약의 상태가 모두 있다
    assert expected <= actual


def test_write_test_endpoints_have_no_response_body(schema: dict[str, Any]) -> None:
    """쓰기 테스트의 204에는 본문 스키마가 없다.

    테스트 코드: IN-058
    """
    # when·then: 204 응답을 읽는다 → content가 없다
    for path in ("/api/v1/settings/storage/test", "/api/v1/auth/setup/storage/test"):
        assert "content" not in schema["paths"][path]["post"]["responses"]["204"]


def test_request_schema_takes_only_a_path(schema: dict[str, Any]) -> None:
    """요청 스키마는 필수 문자열 path 하나만 받는다.

    테스트 코드: IN-058
    """
    # when: 요청 스키마를 읽는다
    request = schema["components"]["schemas"]["StorageSettingsRequest"]

    # then: 속성 path 하나, 필수, 추가 속성 금지다
    assert set(request["properties"]) == {"path"}
    assert request["required"] == ["path"]
    assert request["additionalProperties"] is False


def test_response_schema_has_path_time_and_a_nullable_saver(schema: dict[str, Any]) -> None:
    """응답 스키마는 path·updated_at·updated_by(null 가능)다.

    테스트 코드: IN-058
    """
    # when: 응답 스키마를 읽는다
    response = schema["components"]["schemas"]["StorageSettingsResponse"]

    # then: 세 속성이고 updated_by는 null을 허용한다
    assert set(response["properties"]) == {"path", "updated_at", "updated_by"}
    assert set(response["required"]) == {"path", "updated_at", "updated_by"}
    saver = response["properties"]["updated_by"]
    assert any(option.get("type") == "null" for option in saver["anyOf"])


def test_auth_config_declares_the_storage_step_flag(schema: dict[str, Any]) -> None:
    """인증 설정 응답이 저장 위치 단계 플래그를 선언한다."""
    # when: 스키마를 읽는다
    config = schema["components"]["schemas"]["AuthConfigResponse"]

    # then: needs_storage_setup이 불리언 필수다
    assert config["properties"]["needs_storage_setup"]["type"] == "boolean"
    assert "needs_storage_setup" in config["required"]
