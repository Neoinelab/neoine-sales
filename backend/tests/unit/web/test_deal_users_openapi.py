"""Deal users의 OpenAPI 계약: 등록은 필수 정수, 응답은 null 없는 정수, 수정은 선택.

커밋된 openapi.json과의 일치(드리프트)는 PL-034(`test_openapi_contract.py`)가 검사한다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


@pytest.fixture(scope="module")
def schemas() -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    components: dict[str, Any] = app.openapi()["components"]["schemas"]
    return components


def _has_null(prop: dict[str, Any]) -> bool:
    return any(option.get("type") == "null" for option in prop.get("anyOf", []))


def test_create_request_requires_a_non_null_integer_users(schemas: dict[str, Any]) -> None:
    """등록 요청의 users는 null이 아닌 필수 정수다."""
    # when: 등록 요청 스키마를 읽는다 (전제: OpenAPI 스키마 모음)
    schema = schemas["DealCreateRequest"]

    # then: users가 필수이고 정수이며 null을 허용하지 않는다
    assert "users" in schema["required"]
    assert schema["properties"]["users"]["type"] == "integer"
    assert not _has_null(schema["properties"]["users"])


def test_patch_request_keeps_users_optional_and_nullable_in_the_schema(
    schemas: dict[str, Any],
) -> None:
    """수정 요청의 users는 선택이고 null을 허용한다."""
    # when: 수정 요청 스키마를 읽는다 (전제: OpenAPI 스키마 모음)
    schema = schemas["DealPatchRequest"]

    # then: users가 필수가 아니고 null을 허용한다
    assert "users" not in schema.get("required", [])
    assert _has_null(schema["properties"]["users"])


@pytest.mark.parametrize("name", ["DealRowResponse", "DealDetailResponse"])
def test_responses_require_a_non_null_integer_users(schemas: dict[str, Any], name: str) -> None:
    """응답의 users는 null이 아닌 필수 정수다."""
    # when: 응답 스키마를 읽는다 (전제: OpenAPI 스키마 모음)
    schema = schemas[name]

    # then: users가 필수이고 정수이며 null을 허용하지 않는다
    assert "users" in schema["required"]
    assert schema["properties"]["users"]["type"] == "integer"
    assert not _has_null(schema["properties"]["users"])
