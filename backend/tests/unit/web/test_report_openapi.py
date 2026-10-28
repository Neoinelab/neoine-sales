"""Reports API의 OpenAPI 계약: 응답 코드와 오류 문구의 출처."""

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from app.domain.report.vocabulary import STATEMENT_TIMEOUT_SECONDS
from app.main import create_app
from app.web import error_handlers
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings


def _spec() -> dict[str, Any]:
    settings = make_settings("postgresql+asyncpg://user:pw@localhost:5432/none")
    return dict(create_app(settings=settings, use_cases=FakeUseCases()).openapi())


def test_fields_route_documents_no_422_because_it_takes_no_input() -> None:
    responses = _spec()["paths"]["/api/v1/reports/fields"]["get"]["responses"]

    assert "422" not in responses
    assert {"200", "401"} <= set(responses)


def test_query_route_documents_the_error_responses() -> None:
    responses = _spec()["paths"]["/api/v1/reports/query"]["post"]["responses"]

    assert {"200", "401", "422", "503"} <= set(responses)


def test_timeout_message_takes_its_seconds_from_the_domain_constant() -> None:
    assert f"{STATEMENT_TIMEOUT_SECONDS}초" in error_handlers.REPORT_TIMEOUT_DETAIL
    block = inspect.getsource(error_handlers).split("REPORT_TIMEOUT_DETAIL =", 1)[1]
    block = block.split("\n\n", 1)[0]
    assert "STATEMENT_TIMEOUT_SECONDS" in block  # 문자열 "10초"를 따로 적지 않는다


# ---- 포맷 정리 (2026-10-28) ----

COMMITTED = Path(__file__).resolve().parents[3] / "openapi.json"
SEVEN_FORMATS = ["ymd", "ymd_hm", "year", "quarter", "month", "weekday", "relative"]


def _nullable_format_ref(node: dict[str, Any]) -> bool:
    options = node.get("anyOf", [])
    refs = [o.get("$ref") for o in options]
    return "#/components/schemas/Format" in refs and {"type": "null"} in options


@pytest.mark.parametrize("source", ["app", "committed"])
def test_format_schema_is_nullable_with_seven_date_values(source: str) -> None:
    spec = _spec() if source == "app" else json.loads(COMMITTED.read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]

    assert schemas["Format"]["enum"] == SEVEN_FORMATS
    assert _nullable_format_ref(schemas["ReportResultColumn"]["properties"]["format"])
    assert _nullable_format_ref(schemas["ReportFieldResponse"]["properties"]["default_format"])


def _nullable_unit_ref(node: dict[str, Any]) -> bool:
    options = node.get("anyOf", [])
    refs = [o.get("$ref") for o in options]
    return "#/components/schemas/NumberUnit" in refs and {"type": "null"} in options


@pytest.mark.parametrize("source", ["app", "committed"])
def test_unit_schema_is_a_nullable_number_unit_on_fields_and_result_columns(
    source: str,
) -> None:
    spec = _spec() if source == "app" else json.loads(COMMITTED.read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]

    assert schemas["NumberUnit"]["enum"] == ["krw_thousand"]
    assert _nullable_unit_ref(schemas["ReportFieldResponse"]["properties"]["unit"])
    assert _nullable_unit_ref(schemas["ReportResultColumn"]["properties"]["unit"])
    assert "unit" in schemas["ReportFieldResponse"]["required"]
    assert "unit" in schemas["ReportResultColumn"]["required"]


def test_report_openapi_has_column_sort_and_no_top_level_sort() -> None:
    schemas = _spec()["components"]["schemas"]

    assert "sort" in schemas["ReportColumnRequest"]["properties"]
    assert "sort" not in schemas["ReportQueryRequest"]["properties"]
    assert "ReportSortRequest" not in schemas
