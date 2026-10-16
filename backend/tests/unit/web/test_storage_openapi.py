"""저장 위치 API의 OpenAPI 계약(P2b AC-01·05·18): 경로·메서드·응답 코드·스키마.

커밋된 openapi.json과의 일치(드리프트)는 functional/platform이 검사한다. 이 파일은 새 계약의 핵심을
직접 고정해, 스키마가 갱신되지 않았거나 필드가 빠진 경우를 구체적으로 드러낸다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


def _responses(schema: dict[str, Any], method: str, path: str) -> set[str]:
    return set(schema["paths"][path][method]["responses"])


def test_storage_settings_paths_and_methods(schema: dict[str, Any]) -> None:
    paths = schema["paths"]

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
    assert expected <= _responses(schema, method, path)


def test_write_test_endpoints_have_no_response_body(schema: dict[str, Any]) -> None:
    for path in ("/api/v1/settings/storage/test", "/api/v1/auth/setup/storage/test"):
        assert "content" not in schema["paths"][path]["post"]["responses"]["204"]


def test_request_schema_takes_only_a_path(schema: dict[str, Any]) -> None:
    request = schema["components"]["schemas"]["StorageSettingsRequest"]

    assert set(request["properties"]) == {"path"}
    assert request["required"] == ["path"]
    assert request["additionalProperties"] is False


def test_response_schema_has_path_time_and_a_nullable_saver(schema: dict[str, Any]) -> None:
    response = schema["components"]["schemas"]["StorageSettingsResponse"]

    assert set(response["properties"]) == {"path", "updated_at", "updated_by"}
    assert set(response["required"]) == {"path", "updated_at", "updated_by"}
    saver = response["properties"]["updated_by"]
    assert any(option.get("type") == "null" for option in saver["anyOf"])


def test_auth_config_declares_the_storage_step_flag(schema: dict[str, Any]) -> None:
    config = schema["components"]["schemas"]["AuthConfigResponse"]

    assert config["properties"]["needs_storage_setup"]["type"] == "boolean"
    assert "needs_storage_setup" in config["required"]
