"""Vendor API의 OpenAPI 계약(AC-2·6·14): 경로·메서드, 응답 모양, 폐지된 facets·Solution API."""

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


def test_vendor_paths_and_methods(schema: dict[str, Any]) -> None:
    paths = schema["paths"]
    expected = {
        "/api/v1/vendors": {"get", "post"},
        "/api/v1/vendors/{vendor_id}": {"patch", "delete"},
    }

    for path, methods in expected.items():
        assert set(paths[path]) == methods, path
        for operation in paths[path].values():
            assert operation["tags"] == ["vendors"], path


def test_the_facets_path_is_gone(schema: dict[str, Any]) -> None:
    assert "/api/v1/deals/facets" not in schema["paths"]
    assert "DealFacetsResponse" not in schema["components"]["schemas"]


def test_openapi_has_no_solution_paths_or_schemas(schema: dict[str, Any]) -> None:
    assert not [path for path in schema["paths"] if "/solutions" in path]
    for name in ("SolutionResponse", "SolutionNameRequest"):
        assert name not in schema["components"]["schemas"], name


def test_vendor_response_has_usage_and_no_solutions(schema: dict[str, Any]) -> None:
    schemas = schema["components"]["schemas"]

    assert set(schemas["VendorResponse"]["properties"]) == {
        "id",
        "name",
        "usage_count",
        "created_at",
        "updated_at",
    }


def test_deal_requests_take_vendor_id_and_a_solution_text(schema: dict[str, Any]) -> None:
    schemas = schema["components"]["schemas"]

    for name in ("DealCreateRequest", "DealPatchRequest"):
        props = schemas[name]["properties"]
        assert {"vendor_id", "solution"} <= set(props), name
        assert not {"vendor", "solution_id"} & set(props), name
    assert schemas["DealCreateRequest"]["properties"]["solution"]["type"] == "string"
    assert "solution" in schemas["DealCreateRequest"]["required"]  # 등록 시 필수(Q1 변경)


def test_deal_responses_expose_a_vendor_ref_and_a_solution_string(
    schema: dict[str, Any],
) -> None:
    schemas = schema["components"]["schemas"]

    for name in ("DealRowResponse", "DealDetailResponse"):
        props = schemas[name]["properties"]
        assert {"vendor", "solution"} <= set(props), name
        assert props["solution"]["type"] == "string", name
        assert "solution" in schemas[name]["required"], name
    assert set(schemas["NamedRefResponse"]["properties"]) == {"id", "name"}


def test_deal_search_takes_vendor_id_and_a_solution_text(schema: dict[str, Any]) -> None:
    parameters = schema["paths"]["/api/v1/deals"]["get"]["parameters"]
    by_name = {p["name"]: p for p in parameters}

    assert {"vendor_id", "solution", "quarter", "year"} <= set(by_name)
    assert "solution_id" not in by_name
    assert "vendor" not in by_name
    assert any(
        branch.get("type") == "string" and branch.get("maxLength") == 200
        for branch in by_name["solution"]["schema"].get("anyOf", [by_name["solution"]["schema"]])
    )
