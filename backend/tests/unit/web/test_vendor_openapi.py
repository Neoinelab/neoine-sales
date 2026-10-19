"""Vendor API의 OpenAPI 계약(AC-13·17·25의 핵심): 경로·메서드, 응답 모양, 폐지된 facets."""

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
        "/api/v1/vendors/{vendor_id}/solutions": {"post"},
        "/api/v1/vendors/{vendor_id}/solutions/{solution_id}": {"patch", "delete"},
    }

    for path, methods in expected.items():
        assert set(paths[path]) == methods, path
        for operation in paths[path].values():
            assert operation["tags"] == ["vendors"], path


def test_the_facets_path_is_gone(schema: dict[str, Any]) -> None:
    assert "/api/v1/deals/facets" not in schema["paths"]
    assert "DealFacetsResponse" not in schema["components"]["schemas"]


def test_vendor_response_nests_solutions_with_usage(schema: dict[str, Any]) -> None:
    schemas = schema["components"]["schemas"]

    assert set(schemas["VendorResponse"]["properties"]) == {
        "id",
        "name",
        "usage_count",
        "solutions",
        "created_at",
        "updated_at",
    }
    assert set(schemas["SolutionResponse"]["properties"]) == {
        "id",
        "vendor_id",
        "name",
        "usage_count",
        "created_at",
        "updated_at",
    }


def test_deal_requests_use_vendor_id_and_solution_id_only(schema: dict[str, Any]) -> None:
    schemas = schema["components"]["schemas"]

    for name in ("DealCreateRequest", "DealPatchRequest"):
        props = schemas[name]["properties"]
        assert {"vendor_id", "solution_id"} <= set(props), name
        assert not {"vendor", "solution"} & set(props), name


def test_deal_responses_expose_named_refs(schema: dict[str, Any]) -> None:
    props = schema["components"]["schemas"]["DealRowResponse"]["properties"]

    assert {"vendor", "solution"} <= set(props)
    assert "NamedRefResponse" in schema["components"]["schemas"]
    assert set(schema["components"]["schemas"]["NamedRefResponse"]["properties"]) == {
        "id",
        "name",
    }


def test_deal_search_takes_vendor_id_and_solution_id(schema: dict[str, Any]) -> None:
    params = {p["name"] for p in schema["paths"]["/api/v1/deals"]["get"]["parameters"]}

    assert {"vendor_id", "solution_id", "quarter", "year"} <= params
    assert not {"vendor", "solution"} & params
