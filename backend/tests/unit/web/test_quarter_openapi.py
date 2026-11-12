"""Quarter 다중 선택의 OpenAPI 계약.

`GET /api/v1/deals`·`/dashboard/summary`의 `quarter`는 정수 배열(항목 1~4, 최대 4개), 응답
`DashboardPeriodResponse.quarters`는 필수 정수 배열이다.
`/forecast/summary`의 `quarter`는 단일 정수 그대로다.
`backend/openapi.json` 드리프트는 기존 테스트가 본다.
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


def _quarter_parameter(schema: dict[str, Any], path: str) -> dict[str, Any]:
    parameters = {p["name"]: p for p in schema["paths"][path]["get"]["parameters"]}
    parameter: dict[str, Any] = parameters["quarter"]
    return parameter


@pytest.mark.parametrize("path", ["/api/v1/deals", "/api/v1/dashboard/summary"])
def test_quarter_is_an_optional_array_of_one_to_four_with_at_most_four_items(
    schema: dict[str, Any], path: str
) -> None:
    """quarter 쿼리는 선택 사항인 정수 배열(항목 1~4, 최대 4개)로 문서화된다.

    BDD 밖: Deal 목록·Dashboard 계약이 문서에 남아 있는지 확인한다.
    """
    # given: 앱의 openapi 문서
    # when: 경로의 quarter 파라미터를 읽는다
    parameter = _quarter_parameter(schema, path)
    options = parameter["schema"].get("anyOf", [parameter["schema"]])
    arrays = [o for o in options if o.get("type") == "array"]

    # then: 선택 사항인 쿼리 배열이고 항목은 1~4 정수, 최대 4개, 반복 파라미터다
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
    """Dashboard 기간 응답은 필수 정수 배열 quarters를 가지고 quarter도 남긴다.

    BDD 밖: 응답 계약(DSH-R4)이 문서에 남아 있는지 확인한다.
    """
    # when: 기간 응답 스키마를 읽는다
    period = schema["components"]["schemas"]["DashboardPeriodResponse"]

    # then: quarters는 필수 정수 배열이고 하위 호환 quarter가 남는다
    assert "quarters" in period["required"]
    assert period["properties"]["quarters"]["type"] == "array"
    assert period["properties"]["quarters"]["items"]["type"] == "integer"
    assert "quarter" in period["properties"]  # 하위 호환 필드는 남는다


def test_the_forecast_summary_quarter_stays_a_single_integer(schema: dict[str, Any]) -> None:
    """Forecast 요약의 quarter는 배열이 아닌 단일 정수 그대로다.

    BDD 밖: Dashboard와 달리 Forecast 계약은 바뀌지 않았음을 확인한다.
    """
    # when: Forecast 요약의 quarter 파라미터를 읽는다
    parameter = _quarter_parameter(schema, "/api/v1/forecast/summary")
    options = parameter["schema"].get("anyOf", [parameter["schema"]])

    # then: 배열 형태는 없고 정수 형태만 있다
    assert not [o for o in options if o.get("type") == "array"]
    assert [o for o in options if o.get("type") == "integer"]
