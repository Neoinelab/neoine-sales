"""GET /api/v1/deals의 API 계약 문서(AC-3·8·10·12): 앱이 만든 계약과 커밋된 openapi.json 모두."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
COMMITTED = Path(__file__).resolve().parents[3] / "openapi.json"
SORTS = {
    "name",
    "revenue_amount",
    "revenue_date",
    "last_updated_at",
    "status",
    "owner",
    "customer",
    "partner",
    "vendor",
    "forecast",
}


@pytest.fixture(scope="module", params=["app", "committed"])
def contract(request: pytest.FixtureRequest) -> dict[str, Any]:
    if request.param == "committed":
        loaded: dict[str, Any] = json.loads(COMMITTED.read_text(encoding="utf-8"))
        return loaded
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


@pytest.fixture
def parameters(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    listed = contract["paths"]["/api/v1/deals"]["get"]["parameters"]
    return {p["name"]: p for p in listed}


def _enum_values(schema: dict[str, Any], contract: dict[str, Any]) -> set[str]:
    """스키마의 enum 값. $ref(components)와 anyOf를 따라간다."""
    found: set[str] = set(schema.get("enum", []))
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        found |= _enum_values(contract["components"]["schemas"][name], contract)
    for option in schema.get("anyOf", []):
        found |= _enum_values(option, contract)
    return found


def test_the_bant_query_parameters_are_gone(parameters: dict[str, dict[str, Any]]) -> None:
    assert [name for name in parameters if name.startswith("bant_")] == []


@pytest.mark.parametrize("name", ["overdue", "stale"])
def test_overdue_and_stale_are_optional_booleans_defaulting_to_false(
    parameters: dict[str, dict[str, Any]], name: str
) -> None:
    parameter = parameters[name]

    assert parameter["in"] == "query"
    assert parameter.get("required", False) is False
    assert parameter["schema"]["type"] == "boolean"
    assert parameter["schema"]["default"] is False


def test_sort_documents_the_ten_sortable_values(
    parameters: dict[str, dict[str, Any]], contract: dict[str, Any]
) -> None:
    assert _enum_values(parameters["sort"]["schema"], contract) == SORTS


def test_forecast_key_is_an_array_parameter(parameters: dict[str, dict[str, Any]]) -> None:
    parameter = parameters["forecast_key"]
    options = parameter["schema"].get("anyOf", [parameter["schema"]])
    arrays = [o for o in options if o.get("type") == "array"]
    assert arrays, f"forecast_key must accept an array: {parameter['schema']}"
    array = arrays[0]

    assert parameter["in"] == "query"
    assert parameter.get("required", False) is False
    assert array["items"]["type"] == "string"
    assert array["items"]["maxLength"] == 50
    assert array["maxItems"] == 100
    assert parameter.get("explode", True) is True
