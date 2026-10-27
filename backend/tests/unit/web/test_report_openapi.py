"""Reports API의 OpenAPI 계약: 응답 코드와 오류 문구의 출처."""

import inspect
from typing import Any

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
