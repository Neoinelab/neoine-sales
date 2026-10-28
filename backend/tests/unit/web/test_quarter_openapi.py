"""Quarter 다중 선택의 OpenAPI 계약(AC-10, AC-11).

`GET /api/v1/deals`·`/dashboard/summary`의 `quarter`는 정수 배열(항목 1~4, 최대 4개), 응답
`DashboardPeriodResponse.quarters`는 필수 정수 배열이다.
`/forecast/summary`의 `quarter`는 단일 정수 그대로다.
`backend/openapi.json` 드리프트는 기존 테스트가 본다.
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


def _quarter_parameter(schema: dict[str, Any], path: str) -> dict[str, Any]:
    parameters = {p["name"]: p for p in schema["paths"][path]["get"]["parameters"]}
    parameter: dict[str, Any] = parameters["quarter"]
    return parameter


@pytest.mark.parametrize("path", ["/api/v1/deals", "/api/v1/dashboard/summary"])
def test_quarter_is_an_optional_array_of_one_to_four_with_at_most_four_items(
    schema: dict[str, Any], path: str
) -> None:
    parameter = _quarter_parameter(schema, path)
    options = parameter["schema"].get("anyOf", [parameter["schema"]])
    arrays = [o for o in options if o.get("type") == "array"]
    assert arrays, f"quarter must accept an array: {parameter['schema']}"
    array = arrays[0]

    assert parameter["in"] == "query"
    assert parameter.get("required", False) is False
    assert array["items"]["type"] == "integer"
    assert array["items"]["minimum"] == 1
    assert array["items"]["maximum"] == 4
    assert array["maxItems"] == 4
    assert parameter.get("explode", True) is True


def test_the_dashboard_period_response_requires_an_integer_array_named_quarters(
    schema: dict[str, Any],
) -> None:
    period = schema["components"]["schemas"]["DashboardPeriodResponse"]

    assert "quarters" in period["required"]
    assert period["properties"]["quarters"]["type"] == "array"
    assert period["properties"]["quarters"]["items"]["type"] == "integer"
    assert "quarter" in period["properties"]  # 하위 호환 필드는 남는다


def test_the_forecast_summary_quarter_stays_a_single_integer(schema: dict[str, Any]) -> None:
    parameter = _quarter_parameter(schema, "/api/v1/forecast/summary")
    options = parameter["schema"].get("anyOf", [parameter["schema"]])

    assert not [o for o in options if o.get("type") == "array"]
    assert [o for o in options if o.get("type") == "integer"]
