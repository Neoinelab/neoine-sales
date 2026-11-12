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
from tests.support.app_settings import make_settings


def _spec() -> dict[str, Any]:
    settings = make_settings("postgresql+asyncpg://user:pw@localhost:5432/none")
    return dict(create_app(settings=settings, use_cases=FakeUseCases()).openapi())


def test_fields_route_documents_no_422_because_it_takes_no_input() -> None:
    """필드 목록 경로는 입력이 없어 422를 문서화하지 않는다.

    테스트 코드: RQ-064
    """
    # when: openapi의 필드 목록 경로 응답을 읽는다
    responses = _spec()["paths"]["/api/v1/reports/fields"]["get"]["responses"]

    # then: 422가 없고 200과 401이 있다
    assert "422" not in responses
    assert {"200", "401"} <= set(responses)


def test_query_route_documents_the_error_responses() -> None:
    """조회 경로는 200·401·422·503 응답을 문서화한다.

    테스트 코드: RQ-064
    """
    # when: openapi의 조회 경로 응답을 읽는다
    responses = _spec()["paths"]["/api/v1/reports/query"]["post"]["responses"]

    # then: 200·401·422·503이 있다
    assert {"200", "401", "422", "503"} <= set(responses)


def test_timeout_message_takes_its_seconds_from_the_domain_constant() -> None:
    """시간 초과 문구의 초는 도메인 상수에서 온다.

    테스트 코드: RQ-061
    """
    # when: 시간 제한 오류 문구를 읽는다
    detail = error_handlers.REPORT_TIMEOUT_DETAIL
    # then: 문구에 상수 초가 들어 있다
    assert f"{STATEMENT_TIMEOUT_SECONDS}초" in detail
    # when: 문구를 만드는 소스 블록을 읽는다
    block = inspect.getsource(error_handlers).split("REPORT_TIMEOUT_DETAIL =", 1)[1]
    block = block.split("\n\n", 1)[0]
    # then: 소스가 상수를 쓰고 문자열 10초를 따로 적지 않는다
    assert "STATEMENT_TIMEOUT_SECONDS" in block  # 문자열 "10초"를 따로 적지 않는다


# ---- 포맷·단위 스키마 ----

COMMITTED = Path(__file__).resolve().parents[3] / "openapi.json"
SEVEN_FORMATS = ["ymd", "ymd_hm", "year", "quarter", "month", "weekday", "relative"]


def _nullable_format_ref(node: dict[str, Any]) -> bool:
    options = node.get("anyOf", [])
    refs = [o.get("$ref") for o in options]
    return "#/components/schemas/Format" in refs and {"type": "null"} in options


@pytest.mark.parametrize("source", ["app", "committed"])
def test_format_schema_is_nullable_with_seven_date_values(source: str) -> None:
    """Format 스키마는 날짜 포맷 7개이고 결과 열 포맷과 기본 포맷은 null을 허용한다.

    테스트 코드: RQ-064
    """
    # when: 앱과 커밋된 openapi의 스키마를 읽는다 (전제: 출처 매개변수)
    spec = _spec() if source == "app" else json.loads(COMMITTED.read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]

    # then: Format enum이 7개이고 두 필드가 nullable Format 참조다
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
    """unit 스키마는 필드와 결과 열에서 nullable NumberUnit이고 필수다.

    테스트 코드: RQ-064
    """
    # when: 앱과 커밋된 openapi의 스키마를 읽는다 (전제: 출처 매개변수)
    spec = _spec() if source == "app" else json.loads(COMMITTED.read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]

    # then: NumberUnit은 krw뿐이고 두 스키마의 unit이 nullable 참조이며 필수다
    assert schemas["NumberUnit"]["enum"] == ["krw"]
    assert _nullable_unit_ref(schemas["ReportFieldResponse"]["properties"]["unit"])
    assert _nullable_unit_ref(schemas["ReportResultColumn"]["properties"]["unit"])
    assert "unit" in schemas["ReportFieldResponse"]["required"]
    assert "unit" in schemas["ReportResultColumn"]["required"]


def test_report_openapi_has_column_sort_and_no_top_level_sort() -> None:
    """openapi 요청에는 컬럼 sort가 있고 최상위 sort가 없다.

    테스트 코드: RQ-064
    """
    # when: openapi의 요청 스키마를 읽는다
    schemas = _spec()["components"]["schemas"]

    # then: 컬럼 요청에 sort가 있고 최상위 요청에는 없으며 예전 정렬 스키마도 없다
    assert "sort" in schemas["ReportColumnRequest"]["properties"]
    assert "sort" not in schemas["ReportQueryRequest"]["properties"]
    assert "ReportSortRequest" not in schemas
