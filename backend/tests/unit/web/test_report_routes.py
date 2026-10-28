"""Reports 라우터 (AC1, AC2, AC4, AC12, AC13): FakeUseCases 위의 HTTP 계약과 오류 매핑.

DB 없이 라우터·스키마·오류 매핑·권한을 확인한다. 실제 DB를 지나는 시나리오는 functional(reports/)이
맡는다. 조회 결과는 Fake `ReportQueryRunner`가 돌려주는 고정 값이다.
"""

import re
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.ports.report_query_runner import ReportQueryTimeoutError
from app.domain.auth.principal import Role
from app.domain.report.catalog import FIELD_CATALOG
from app.main import create_app
from tests.factories_auth import make_principal
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import CSRF_HEADER, make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
FIELDS = "/api/v1/reports/fields"
QUERY = "/api/v1/reports/query"
TIMEOUT_DETAIL = "조회가 10초 안에 끝나지 않았습니다. 조건을 좁히거나 컬럼을 줄이세요"
VALID = {"columns": [{"field": "deal.code"}]}


@asynccontextmanager
async def _client(
    use_cases: FakeUseCases, *, role: Role | None = None, csrf: bool = True
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    cookies = {}
    if role is not None:
        cookies[SESSION_COOKIE] = await use_cases.login_as(make_principal("root", role))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER if csrf else {},
        cookies=cookies,
    ) as http:
        yield http


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


# ---- GET /fields (AC1) ----


async def test_fields_route_returns_the_catalog_shape() -> None:
    async with _client(FakeUseCases(), role=Role.USER) as http:
        response = await http.get(FIELDS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "limits",
        "entities",
        "formats",
        "operators",
        "aggregates",
        "relative_periods",
        "fields",
    }
    assert [f["key"] for f in body["fields"]] == [f.key for f in FIELD_CATALOG]
    assert [e["key"] for e in body["entities"]] == ["deal", "action"]


async def test_fields_route_documents_the_limits() -> None:
    async with _client(FakeUseCases(), role=Role.USER) as http:
        limits = (await http.get(FIELDS)).json()["limits"]

    assert limits == {
        "columns_min": 1,
        "columns_max": 30,
        "conditions_max": 20,
        "row_limits": [100, 1000, 10000],
        "default_row_limit": 1000,
        "statement_timeout_seconds": 10,
        "text_value_max": 200,
        "list_value_max": 100,
        "last_n_days_max": 3650,
        "label_max": 100,
        "prefix_max": 200,
    }


async def test_amount_field_has_the_documented_shape() -> None:
    async with _client(FakeUseCases(), role=Role.USER) as http:
        fields = {f["key"]: f for f in (await http.get(FIELDS)).json()["fields"]}

    assert fields["deal.amount"] == {
        "key": "deal.amount",
        "label": "금액",
        "entity": "deal",
        "type": "number",
        "formats": [],
        "default_format": None,
        "unit": "krw_thousand",
        "operators": ["eq", "ne", "gt", "gte", "lt", "lte", "between"],
        "aggregates": ["sum", "avg", "min", "max"],
        "default_aggregate": "sum",
        "groupable": True,
        "filterable": True,
        "requires_grouping": False,
        "deal_number": True,
        "value_kind": None,
        "options": None,
        "options_source": None,
        "options_category": None,
    }


async def test_code_fields_carry_static_options_or_an_options_source() -> None:
    async with _client(FakeUseCases(), role=Role.USER) as http:
        fields = {f["key"]: f for f in (await http.get(FIELDS)).json()["fields"]}

    assert fields["deal.forecast_outcome"]["value_kind"] == "key"
    assert fields["deal.forecast_outcome"]["options"] == [
        {"value": "open", "label": "Open"},
        {"value": "won", "label": "Won"},
        {"value": "lost", "label": "Lost"},
    ]
    assert fields["deal.vendor"]["value_kind"] == "id"
    assert fields["deal.vendor"]["options"] is None
    assert fields["deal.vendor"]["options_source"] == "vendors"
    assert fields["deal.bant_need"]["options_source"] == "bant_labels"
    assert fields["deal.bant_need"]["options_category"] == "need"


async def test_fields_route_requires_login() -> None:
    async with _client(FakeUseCases()) as http:
        response = await http.get(FIELDS)

    assert response.status_code == 401
    assert str(response.json()["type"]).endswith("unauthenticated")


# ---- POST /query: 권한 (AC2) ----


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_can_query_without_write_permission(role: Role) -> None:
    async with _client(FakeUseCases(), role=role) as http:
        response = await http.post(QUERY, json=VALID)

    assert response.status_code == 200, response.text


async def test_query_requires_login() -> None:
    async with _client(FakeUseCases()) as http:
        response = await http.post(QUERY, json=VALID)

    assert response.status_code == 401
    assert str(response.json()["type"]).endswith("unauthenticated")


async def test_query_without_the_csrf_header_is_403_csrf() -> None:
    async with _client(FakeUseCases(), role=Role.USER, csrf=False) as http:
        response = await http.post(QUERY, json=VALID)

    assert response.status_code == 403
    assert str(response.json()["type"]).endswith("csrf")


# ---- POST /query: 결과 (AC13) ----


async def test_query_route_returns_the_result_shape() -> None:
    use_cases = FakeUseCases()
    use_cases.uow.reports.respond_with(
        [
            [
                "20261016-0001",
                datetime(2026, 3, 31, 15, 30, tzinfo=UTC),
                date(2026, 6, 30),
                5,
                2.5,
                None,
            ]
        ],
        total_count=7,
        sql="SELECT demo",
        elapsed_ms=21,
    )
    body_in = {
        "columns": [
            {"field": "deal.code"},
            {"field": "deal.created_at"},
            {"field": "deal.expected_close"},
            {"field": "deal.users"},
            {"field": "deal.users"},
            {"field": "action.memo"},
        ],
        "row_limit": 100,
    }
    async with _client(use_cases, role=Role.USER) as http:
        response = await http.post(QUERY, json=body_in)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "row_scope",
        "action_filter",
        "deal_numbers_once",
        "columns",
        "rows",
        "total_count",
        "truncated",
        "row_limit",
        "sql",
        "elapsed_ms",
        "today",
        "totals",
    }
    assert (body["row_scope"], body["action_filter"], body["deal_numbers_once"]) == (
        "action",
        "join",
        False,
    )
    assert body["rows"] == [
        ["20261016-0001", "2026-04-01T00:30:00+09:00", "2026-06-30", 5, 2.5, None]
    ]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", body["today"])
    assert (body["total_count"], body["truncated"], body["row_limit"]) == (7, True, 100)
    assert (body["sql"], body["elapsed_ms"], body["totals"]) == ("SELECT demo", 21, None)


async def test_query_route_describes_each_column() -> None:
    use_cases = FakeUseCases()
    body_in = {
        "columns": [
            {"field": "deal.vendor", "group": True, "label": "벤더"},
            {"field": "deal.amount", "aggregate": "sum"},
        ]
    }
    async with _client(use_cases, role=Role.USER) as http:
        columns = (await http.post(QUERY, json=body_in)).json()["columns"]

    assert columns == [
        {
            "index": 0,
            "field": "deal.vendor",
            "label": "벤더",
            "entity": "deal",
            "type": "code",
            "value_type": "text",
            "format": None,
            "unit": None,
            "prefix_length": None,
            "group": True,
            "aggregate": None,
        },
        {
            "index": 1,
            "field": "deal.amount",
            "label": "금액",
            "entity": "deal",
            "type": "number",
            "value_type": "integer",
            "format": None,
            "unit": "krw_thousand",
            "prefix_length": None,
            "group": False,
            "aggregate": "sum",
        },
    ]


async def test_query_route_returns_grouped_totals() -> None:
    use_cases = FakeUseCases()
    use_cases.uow.reports.respond_with([["SAP", 10]], totals=[None, 10])
    body_in = {"columns": [{"field": "deal.vendor", "group": True}, {"field": "deal.amount"}]}
    async with _client(use_cases, role=Role.USER) as http:
        body = (await http.post(QUERY, json=body_in)).json()

    assert body["totals"] == [None, 10]


async def test_query_route_passes_the_whole_definition_to_the_use_case() -> None:
    use_cases = FakeUseCases()
    body_in = {
        "columns": [
            {"field": "deal.code"},
            {"field": "deal.name", "label": " 이름 ", "sort": "desc"},
        ],
        "conditions": [{"field": "deal.amount", "operator": "gte", "value": 5}],
        "combine": "or",
        "row_limit": 10000,
    }
    async with _client(use_cases, role=Role.USER) as http:
        await http.post(QUERY, json=body_in)

    (call,) = use_cases.uow.reports.calls
    definition = call.definition
    assert [c.label for c in definition.columns] == ["Deal code", "이름"]
    assert str(definition.combine) == "or"
    assert [str(k.direction) for k in definition.sort_keys()] == ["desc"]
    assert definition.sort_keys()[0].column == 1
    assert definition.row_limit == 10000
    assert call.conditions[0].condition.field.key == "deal.amount"


# ---- POST /query: 오류 ----


async def test_invalid_definition_returns_422_invalid_report_with_errors() -> None:
    body_in = {
        "columns": [
            {"field": "deal.code"},
            {"field": "deal.password"},
            {"field": "deal.amount", "format": "quarter"},
        ],
        "conditions": [{"field": "deal.name", "operator": "gt", "value": "x"}],
    }
    async with _client(FakeUseCases(), role=Role.USER) as http:
        response = await http.post(QUERY, json=body_in)

    assert response.status_code == 422
    body = response.json()
    assert str(body["type"]).endswith("invalid-report")
    assert body["title"] == "Invalid Report"
    assert [(e["location"], e["code"]) for e in body["errors"]] == [
        (["columns", 1, "field"], "unknown-field"),
        (["columns", 2, "format"], "format-not-allowed"),
        (["conditions", 0, "operator"], "operator-not-allowed"),
    ]
    assert all(isinstance(e["message"], str) and e["message"] for e in body["errors"])
    assert body["detail"] == body["errors"][0]["message"]


async def test_query_passes_column_sort_to_the_definition() -> None:
    use_cases = FakeUseCases()
    body_in = {"columns": [{"field": "deal.code"}, {"field": "deal.name", "sort": "desc"}]}
    async with _client(use_cases, role=Role.USER) as http:
        response = await http.post(QUERY, json=body_in)

    assert response.status_code == 200
    (call,) = use_cases.uow.reports.calls
    assert [c.sort for c in call.definition.columns] == [None, "desc"]


@pytest.mark.parametrize("sort", ["asc", "desc", None])
async def test_column_sort_asc_desc_null_or_omitted_is_accepted(sort: str | None) -> None:
    body_in = {"columns": [{"field": "deal.code", "sort": sort}, {"field": "deal.name"}]}
    async with _client(FakeUseCases(), role=Role.USER) as http:
        response = await http.post(QUERY, json=body_in)

    assert response.status_code == 200


@pytest.mark.parametrize("sort", ["ASC", "up", ""])
async def test_unknown_column_sort_is_invalid_report_at_column(sort: str) -> None:
    body_in = {"columns": [{"field": "deal.code"}, {"field": "deal.name", "sort": sort}]}
    async with _client(FakeUseCases(), role=Role.USER) as http:
        response = await http.post(QUERY, json=body_in)

    assert response.status_code == 422
    body = response.json()
    assert str(body["type"]).endswith("invalid-report")
    assert [(e["location"], e["code"]) for e in body["errors"]] == [
        (["columns", 1, "sort"], "sort-invalid")
    ]
    assert body["errors"][0]["message"] == "정렬은 asc 또는 desc만 쓸 수 있습니다"


async def test_every_unknown_column_sort_is_reported() -> None:
    body_in = {
        "columns": [
            {"field": "deal.code", "sort": "up"},
            {"field": "deal.name", "sort": "asc"},
            {"field": "deal.vendor", "sort": "DESC"},
        ]
    }
    async with _client(FakeUseCases(), role=Role.USER) as http:
        response = await http.post(QUERY, json=body_in)

    assert [e["location"] for e in response.json()["errors"]] == [
        ["columns", 0, "sort"],
        ["columns", 2, "sort"],
    ]


async def test_invalid_definition_does_not_run_the_query() -> None:
    use_cases = FakeUseCases()
    async with _client(use_cases, role=Role.USER) as http:
        await http.post(QUERY, json={"columns": []})

    assert use_cases.uow.reports.calls == []


@pytest.mark.parametrize(
    "body_in",
    [
        {},
        {"columns": None},
        {"columns": "deal.code"},
        {"columns": ["deal.code"]},
        {"columns": [{}]},
        {"columns": [{"field": 5}]},
        {"columns": [{"field": "deal.code", "unknown": 1}]},
        {"columns": [{"field": "deal.code"}], "unknown": 1},
        {"columns": [{"field": "deal.code"}], "conditions": "x"},
        {"columns": [{"field": "deal.code"}], "conditions": [{"field": "deal.name"}]},
        {"columns": [{"field": "deal.code"}], "sort": {"direction": "asc"}},
        {"columns": [{"field": "deal.code"}], "sort": {"column": 0, "direction": "asc"}},
        {"columns": [{"field": "deal.code"}], "sort": None},
        {"columns": [{"field": "deal.code", "sort": 1}]},
        {"columns": [{"field": "deal.code", "sort": True}]},
        {"columns": [{"field": "deal.code", "sort": {}}]},
        {"columns": [{"field": "deal.code"}], "group": "yes"},
    ],
    ids=[
        "empty",
        "columns-null",
        "columns-string",
        "columns-strings",
        "column-without-field",
        "field-not-string",
        "column-unknown-attr",
        "top-unknown-attr",
        "conditions-string",
        "condition-without-operator",
        "top-level-sort-without-column",
        "top-level-sort-object",
        "top-level-sort-null",
        "column-sort-number",
        "column-sort-bool",
        "column-sort-object",
        "unknown-top-group",
    ],
)
async def test_malformed_json_shape_returns_request_validation(body_in: object) -> None:
    async with _client(FakeUseCases(), role=Role.USER) as http:
        response = await http.post(QUERY, json=body_in)

    assert response.status_code == 422
    assert str(response.json()["type"]).endswith("request-validation")


async def test_timeout_returns_503_report_timeout_with_a_fixed_message() -> None:
    use_cases = FakeUseCases()
    use_cases.uow.reports.error = ReportQueryTimeoutError("canceling statement: secret detail")
    async with _client(use_cases, role=Role.USER) as http:
        response = await http.post(QUERY, json=VALID)

    assert response.status_code == 503
    body = response.json()
    assert str(body["type"]).endswith("report-timeout")
    assert body["title"] == "Report Timeout"
    assert body["detail"] == TIMEOUT_DETAIL
    assert "secret" not in response.text


# ---- 포맷 정리 (2026-10-28) ----


LEGACY_NUMBER_FORMATS = ["thousands", "krw_thousand", "krw_million", "decimal1", "percent_share"]


@pytest.mark.parametrize(
    ("field", "legacy"),
    [("deal.name", x) for x in ["as_is", "prefix", "name", "key"]]
    + [("deal.amount", x) for x in LEGACY_NUMBER_FORMATS]
    + [("deal.name", x) for x in LEGACY_NUMBER_FORMATS],
)
async def test_query_with_legacy_format_returns_invalid_report(field: str, legacy: str) -> None:
    body_in = {"columns": [{"field": field, "format": legacy}]}
    async with _client(FakeUseCases(), role=Role.USER) as http:
        response = await http.post(QUERY, json=body_in)

    assert response.status_code == 422
    body = response.json()
    assert str(body["type"]).endswith("invalid-report")
    assert [(e["location"], e["code"]) for e in body["errors"]] == [
        (["columns", 0, "format"], "format-not-allowed")
    ]
    assert body["errors"][0]["message"] == "이 필드는 포맷을 고를 수 없습니다"


async def test_query_with_format_on_a_text_field_says_it_cannot_be_chosen() -> None:
    body_in = {"columns": [{"field": "deal.name", "format": "quarter"}]}
    async with _client(FakeUseCases(), role=Role.USER) as http:
        body = (await http.post(QUERY, json=body_in)).json()

    assert body["errors"][0]["message"] == "이 필드는 포맷을 고를 수 없습니다"


@pytest.mark.parametrize("length", [0, 201, "20", 1.5, True])
async def test_query_with_bad_prefix_length_returns_invalid_report(length: object) -> None:
    body_in = {"columns": [{"field": "deal.name", "prefix_length": length}]}
    async with _client(FakeUseCases(), role=Role.USER) as http:
        response = await http.post(QUERY, json=body_in)

    assert response.status_code == 422
    errors = response.json()["errors"]
    assert [(e["location"], e["code"]) for e in errors] == [
        (["columns", 0, "prefix_length"], "value-invalid")
    ]
    assert errors[0]["message"] == "앞 N자의 N은 1~200의 정수여야 합니다"


async def test_result_column_format_is_null_for_code_field_and_carries_prefix_length() -> None:
    body_in = {
        "columns": [
            {"field": "deal.status", "prefix_length": 4},
            {"field": "deal.name"},
            {"field": "deal.amount", "prefix_length": 200},
        ]
    }
    async with _client(FakeUseCases(), role=Role.USER) as http:
        columns = (await http.post(QUERY, json=body_in)).json()["columns"]

    assert [(c["format"], c["prefix_length"]) for c in columns] == [
        (None, 4),
        (None, None),
        (None, 200),
    ]


async def test_catalog_formatless_fields() -> None:
    async with _client(FakeUseCases(), role=Role.USER) as http:
        body = (await http.get(FIELDS)).json()

    fields = body["fields"]
    formatless = [f for f in fields if f["type"] in {"text", "code", "user", "number"}]
    assert formatless
    assert all(f["formats"] == [] and f["default_format"] is None for f in formatless)
    assert [f["key"] for f in body["formats"]] == [
        "ymd",
        "ymd_hm",
        "year",
        "quarter",
        "month",
        "weekday",
        "relative",
    ]
    assert {f["key"] for f in body["formats"] if f["affects_query"]} == {
        "ymd",
        "year",
        "quarter",
        "month",
    }


async def test_catalog_only_amount_has_a_unit() -> None:
    async with _client(FakeUseCases(), role=Role.USER) as http:
        fields = (await http.get(FIELDS)).json()["fields"]

    assert all("unit" in f for f in fields)
    assert {f["key"]: f["unit"] for f in fields if f["unit"] is not None} == {
        "deal.amount": "krw_thousand"
    }
    assert len(fields) == 40
