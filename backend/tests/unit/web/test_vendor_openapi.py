"""Vendor API의 OpenAPI 계약: 경로·메서드, 응답 모양, 폐지된 facets·Solution API."""

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


def test_vendor_paths_and_methods(schema: dict[str, Any]) -> None:
    """Vendor 경로와 메서드, 태그가 계약과 같다."""
    # when: OpenAPI 경로를 살펴본다
    paths = schema["paths"]
    expected = {
        "/api/v1/vendors": {"get", "post"},
        "/api/v1/vendors/{vendor_id}": {"patch", "delete"},
    }

    # then: vendors 두 경로의 메서드가 맞고 태그가 vendors다
    for path, methods in expected.items():
        assert set(paths[path]) == methods, path
        for operation in paths[path].values():
            assert operation["tags"] == ["vendors"], path


def test_the_facets_path_is_gone(schema: dict[str, Any]) -> None:
    """폐지된 Deal facets 경로와 스키마가 OpenAPI에 없다."""
    # when: OpenAPI를 살펴본다
    assert "/api/v1/deals/facets" not in schema["paths"]
    # then: facets 경로와 스키마가 없다
    assert "DealFacetsResponse" not in schema["components"]["schemas"]


def test_openapi_has_no_solution_paths_or_schemas(schema: dict[str, Any]) -> None:
    """OpenAPI에 Solution 관리 경로와 스키마가 없다.

    테스트 코드: CL-062
    """
    # when: OpenAPI 문서를 살펴본다
    assert not [path for path in schema["paths"] if "/solutions" in path]
    # then: '/solutions' 경로와 Solution 스키마가 없다
    for name in ("SolutionResponse", "SolutionNameRequest"):
        assert name not in schema["components"]["schemas"], name


def test_vendor_response_has_usage_and_no_solutions(schema: dict[str, Any]) -> None:
    """Vendor 응답 스키마는 사용 수를 가지고 solutions는 없다.

    테스트 코드: CL-062
    """
    # when: Vendor 응답 스키마를 살펴본다
    schemas = schema["components"]["schemas"]

    # then: 키가 id, name, usage_count, created_at, updated_at뿐이다
    assert set(schemas["VendorResponse"]["properties"]) == {
        "id",
        "name",
        "usage_count",
        "created_at",
        "updated_at",
    }


def test_deal_requests_take_vendor_id_and_a_solution_text(schema: dict[str, Any]) -> None:
    """Deal 요청은 vendor_id와 Solution 텍스트를 받고, 등록에서 vendor_id만 필수다.

    테스트 코드: DE-010
    """
    # given: OpenAPI 스키마
    schemas = schema["components"]["schemas"]

    # when: Deal 등록·수정 요청 스키마를 살펴본다
    for name in ("DealCreateRequest", "DealPatchRequest"):
        # then: vendor_id·solution이 있고 예전 필드는 없다
        props = schemas[name]["properties"]
        assert {"vendor_id", "solution"} <= set(props), name
        assert not {"vendor", "solution_id"} & set(props), name
    create = schemas["DealCreateRequest"]
    # 등록: vendor_id는 필수 정수(null 불가), solution은 선택이고 null·생략을 받는다
    assert create["properties"]["vendor_id"]["type"] == "integer"
    assert "vendor_id" in create["required"]
    assert "solution" not in create["required"]
    kinds = {part.get("type") for part in create["properties"]["solution"]["anyOf"]}
    assert kinds == {"string", "null"}


def test_deal_responses_expose_a_vendor_ref_and_a_solution_string(
    schema: dict[str, Any],
) -> None:
    """Deal 응답은 Vendor 참조와 Solution 문자열을 싣는다."""
    # given: OpenAPI 스키마
    schemas = schema["components"]["schemas"]

    # when: Deal 응답 스키마를 살펴본다
    for name in ("DealRowResponse", "DealDetailResponse"):
        # then: vendor·solution이 있고 solution은 필수 문자열이다
        props = schemas[name]["properties"]
        assert {"vendor", "solution"} <= set(props), name
        assert props["solution"]["type"] == "string", name
        assert "solution" in schemas[name]["required"], name
    assert set(schemas["NamedRefResponse"]["properties"]) == {"id", "name"}


def test_deal_search_takes_vendor_id_and_a_solution_text(schema: dict[str, Any]) -> None:
    """Deal 검색은 vendor_id와 Solution 텍스트 조건을 받는다."""
    # given: Deal 목록 검색 파라미터
    parameters = schema["paths"]["/api/v1/deals"]["get"]["parameters"]
    # when: 파라미터 이름을 살펴본다
    by_name = {p["name"]: p for p in parameters}

    # then: vendor_id·solution이 있고 예전 파라미터는 없다
    assert {"vendor_id", "solution", "quarter", "year"} <= set(by_name)
    assert "solution_id" not in by_name
    assert "vendor" not in by_name
    assert any(
        branch.get("type") == "string" and branch.get("maxLength") == 200
        for branch in by_name["solution"]["schema"].get("anyOf", [by_name["solution"]["schema"]])
    )
