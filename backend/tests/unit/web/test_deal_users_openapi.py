"""Deal users의 OpenAPI 계약(AC-9·10): 등록은 필수 정수, 응답은 null 없는 정수, 수정은 선택.

커밋된 openapi.json과의 일치(드리프트)는 functional/platform이 검사한다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


@pytest.fixture(scope="module")
def schemas() -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    components: dict[str, Any] = app.openapi()["components"]["schemas"]
    return components


def _has_null(prop: dict[str, Any]) -> bool:
    return any(option.get("type") == "null" for option in prop.get("anyOf", []))


def test_create_request_requires_a_non_null_integer_users(schemas: dict[str, Any]) -> None:
    schema = schemas["DealCreateRequest"]

    assert "users" in schema["required"]
    assert schema["properties"]["users"]["type"] == "integer"
    assert not _has_null(schema["properties"]["users"])


def test_patch_request_keeps_users_optional_and_nullable_in_the_schema(
    schemas: dict[str, Any],
) -> None:
    schema = schemas["DealPatchRequest"]

    assert "users" not in schema.get("required", [])
    assert _has_null(schema["properties"]["users"])


@pytest.mark.parametrize("name", ["DealRowResponse", "DealDetailResponse"])
def test_responses_require_a_non_null_integer_users(schemas: dict[str, Any], name: str) -> None:
    schema = schemas[name]

    assert "users" in schema["required"]
    assert schema["properties"]["users"]["type"] == "integer"
    assert not _has_null(schema["properties"]["users"])
