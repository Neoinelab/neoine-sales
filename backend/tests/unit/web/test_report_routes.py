"""Reports 라우터: FakeUseCases 위의 HTTP 계약과 오류 매핑.

DB 없이 라우터·스키마·오류 매핑·권한을 확인한다. 조회 결과는 Fake `ReportQueryRunner`가 돌려주는
고정 값이다.
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
from tests.support.app_settings import CSRF_HEADER, make_settings

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


# ---- GET /fields ----


async def test_fields_route_returns_the_catalog_shape() -> None:
    """로그인한 사용자는 필드 카탈로그를 받는다.

    테스트 코드: RQ-001, RQ-002
    """
    # given: 로그인한 user 역할 사용자
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 필드 목록을 요청한다
        response = await http.get(FIELDS)

    # then: 200이고 본문 키 7개, 필드 key 순서는 카탈로그와 같고 엔터티는 deal·action이다
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
    """필드 목록 응답의 한도 값은 설계와 같다.

    테스트 코드: RQ-007
    """
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 필드 목록을 요청한다 (전제: 로그인한 user)
        limits = (await http.get(FIELDS)).json()["limits"]

    # then: 컬럼 1~30, 조건 20, 행 수 100·1000·10000, 기본 1000, 제한 10초 등이다
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
    """금액 필드의 응답 모양은 문서와 같다.

    테스트 코드: RQ-004
    """
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 필드 목록을 요청한다 (전제: 로그인한 user)
        fields = {f["key"]: f for f in (await http.get(FIELDS)).json()["fields"]}

    # then: 금액 필드는 포맷 없음, 단위 krw, 숫자 연산자·집계, 기본 집계 합계, Deal 숫자다
    assert fields["deal.amount"] == {
        "key": "deal.amount",
        "label": "금액",
        "entity": "deal",
        "type": "number",
        "formats": [],
        "default_format": None,
        "unit": "krw",
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
    """코드 필드는 정적 선택지나 선택지 출처를 알린다.

    테스트 코드: RQ-006
    """
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 필드 목록을 요청한다 (전제: 로그인한 user)
        fields = {f["key"]: f for f in (await http.get(FIELDS)).json()["fields"]}

    # then: Forecast 구분은 key 선택지, Vendor는 id 출처, BANT Need는 출처와 분류를 가진다
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
    """로그인하지 않고 필드 목록을 요청하면 401이다.

    테스트 코드: RQ-001
    """
    async with _client(FakeUseCases()) as http:
        # when: 로그인 없이 필드 목록을 요청한다
        response = await http.get(FIELDS)

    # then: 401 unauthenticated다
    assert response.status_code == 401
    assert str(response.json()["type"]).endswith("unauthenticated")


# ---- POST /query: 권한 ----


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_can_query_without_write_permission(role: Role) -> None:
    """모든 역할이 쓰기 권한 없이 조회를 실행한다.

    테스트 코드: RQ-008
    """
    async with _client(FakeUseCases(), role=role) as http:
        # when: 역할 하나로 조회를 실행한다 (전제: 역할 매개변수)
        response = await http.post(QUERY, json=VALID)

    # then: 200이다
    assert response.status_code == 200, response.text


async def test_query_requires_login() -> None:
    """로그인하지 않고 조회하면 401이다.

    테스트 코드: RQ-008
    """
    async with _client(FakeUseCases()) as http:
        # when: 로그인 없이 조회한다
        response = await http.post(QUERY, json=VALID)

    # then: 401 unauthenticated다
    assert response.status_code == 401
    assert str(response.json()["type"]).endswith("unauthenticated")


async def test_query_without_the_csrf_header_is_403_csrf() -> None:
    """CSRF 헤더 없이 조회하면 403 csrf다.

    테스트 코드: RQ-008
    """
    async with _client(FakeUseCases(), role=Role.USER, csrf=False) as http:
        # when: CSRF 헤더 없이 조회한다 (전제: 로그인한 user)
        response = await http.post(QUERY, json=VALID)

    # then: 403 csrf다
    assert response.status_code == 403
    assert str(response.json()["type"]).endswith("csrf")


# ---- POST /query: 결과 ----


async def test_query_route_returns_the_result_shape() -> None:
    """조회 응답은 정해진 키와 값 표기(ISO 날짜, 서버 오프셋 시각, 숫자)를 가진다.

    테스트 코드: RQ-045
    """
    # given: 한 행을 돌려주는 조회 Port와 Action 컬럼이 있는 요청
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
        # when: 조회한다 (전제: 로그인한 user)
        response = await http.post(QUERY, json=body_in)

    # then: 응답 키 12개, 행 범위 Action·JOIN, 시각은 +09:00, 날짜는 ISO, 총 7행·잘림이다
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
    """조회 응답의 열은 적용된 필드·값 형식·단위·집계를 설명한다.

    테스트 코드: RQ-062
    """
    use_cases = FakeUseCases()
    # given: 그룹 컬럼과 금액 합계 컬럼의 요청
    body_in = {
        "columns": [
            {"field": "deal.vendor", "group": True, "label": "벤더"},
            {"field": "deal.amount", "aggregate": "sum"},
        ]
    }
    async with _client(use_cases, role=Role.USER) as http:
        # when: 조회한다 (전제: 로그인한 user)
        columns = (await http.post(QUERY, json=body_in)).json()["columns"]

    # then: 열마다 index·필드·이름·엔터티·형식·value_type·단위·집계가 설명된다
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
            "unit": "krw",
            "prefix_length": None,
            "group": False,
            "aggregate": "sum",
        },
    ]


async def test_query_route_returns_grouped_totals() -> None:
    """그룹핑 조회의 합계 행이 응답에 담긴다.

    테스트 코드: RQ-055
    """
    use_cases = FakeUseCases()
    # given: 합계 행을 돌려주는 조회 Port
    use_cases.uow.reports.respond_with([["SAP", 10]], totals=[None, 10])
    body_in = {"columns": [{"field": "deal.vendor", "group": True}, {"field": "deal.amount"}]}
    async with _client(use_cases, role=Role.USER) as http:
        # when: 그룹핑 조회를 한다 (전제: 로그인한 user)
        body = (await http.post(QUERY, json=body_in)).json()

    # then: 합계 행이 [None, 10]이다
    assert body["totals"] == [None, 10]


async def test_query_route_passes_the_whole_definition_to_the_use_case() -> None:
    """요청의 표시 이름·정렬·조건·결합·행 수 제한이 정의로 전달된다.

    테스트 코드: RQ-013
    """
    use_cases = FakeUseCases()
    # given: 표시 이름에 공백이 있는 컬럼, 정렬, 조건, or 결합, 행 수 10000의 요청
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
        # when: 조회한다 (전제: 로그인한 user)
        await http.post(QUERY, json=body_in)

    # then: 표시 이름은 다듬어지고 결합 or, 정렬 키 desc, 행 수 10000, 조건 필드가 그대로다
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
    """정의 위반은 모두 모아 위치·code·문구와 함께 422 invalid-report로 알린다.

    테스트 코드: RQ-010
    """
    # given: 모르는 필드, 틀린 포맷, 틀린 연산자가 섞인 요청
    body_in = {
        "columns": [
            {"field": "deal.code"},
            {"field": "deal.password"},
            {"field": "deal.amount", "format": "quarter"},
        ],
        "conditions": [{"field": "deal.name", "operator": "gt", "value": "x"}],
    }
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 조회한다 (전제: 로그인한 user)
        response = await http.post(QUERY, json=body_in)

    # then: 422 invalid-report이고 위반 세 개가 순서대로이며 detail은 첫 위반 문구다
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
    """컬럼 sort는 정의로 전달된다.

    테스트 코드: RQ-021
    """
    use_cases = FakeUseCases()
    # given: 둘째 컬럼을 내림차순으로 정렬하는 요청
    body_in = {"columns": [{"field": "deal.code"}, {"field": "deal.name", "sort": "desc"}]}
    async with _client(use_cases, role=Role.USER) as http:
        # when: 조회한다 (전제: 로그인한 user)
        response = await http.post(QUERY, json=body_in)

    # then: 200이고 정의의 컬럼 sort는 [None, "desc"]다
    assert response.status_code == 200
    (call,) = use_cases.uow.reports.calls
    assert [c.sort for c in call.definition.columns] == [None, "desc"]


@pytest.mark.parametrize("sort", ["asc", "desc", None])
async def test_column_sort_asc_desc_null_or_omitted_is_accepted(sort: str | None) -> None:
    """컬럼 sort asc·desc·null·생략은 받아들여진다.

    테스트 코드: RQ-021
    """
    # given: 정렬 값을 준 요청 (매개변수)
    body_in = {"columns": [{"field": "deal.code", "sort": sort}, {"field": "deal.name"}]}
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 조회한다 (전제: 로그인한 user)
        response = await http.post(QUERY, json=body_in)

    # then: 200이다
    assert response.status_code == 200


@pytest.mark.parametrize("sort", ["ASC", "up", ""])
async def test_unknown_column_sort_is_invalid_report_at_column(sort: str) -> None:
    """틀린 컬럼 sort는 그 컬럼 위치의 sort-invalid 422다.

    테스트 코드: RQ-021
    """
    # given: 둘째 컬럼의 정렬 값이 틀린 요청 (매개변수)
    body_in = {"columns": [{"field": "deal.code"}, {"field": "deal.name", "sort": sort}]}
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 조회한다 (전제: 로그인한 user)
        response = await http.post(QUERY, json=body_in)

    # then: invalid-report이고 위반은 컬럼 1 sort 위치의 sort-invalid 하나와 고정 문구다
    assert response.status_code == 422
    body = response.json()
    assert str(body["type"]).endswith("invalid-report")
    assert [(e["location"], e["code"]) for e in body["errors"]] == [
        (["columns", 1, "sort"], "sort-invalid")
    ]
    assert body["errors"][0]["message"] == "정렬은 asc 또는 desc만 쓸 수 있습니다"


async def test_every_unknown_column_sort_is_reported() -> None:
    """틀린 컬럼 sort는 컬럼마다 모두 알린다.

    테스트 코드: RQ-021
    """
    # given: 첫째·셋째 컬럼의 정렬이 틀린 요청
    body_in = {
        "columns": [
            {"field": "deal.code", "sort": "up"},
            {"field": "deal.name", "sort": "asc"},
            {"field": "deal.vendor", "sort": "DESC"},
        ]
    }
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 조회한다 (전제: 로그인한 user)
        response = await http.post(QUERY, json=body_in)

    # then: 위반 위치는 컬럼 0과 컬럼 2의 sort다
    assert [e["location"] for e in response.json()["errors"]] == [
        ["columns", 0, "sort"],
        ["columns", 2, "sort"],
    ]


async def test_invalid_definition_does_not_run_the_query() -> None:
    """정의 위반이면 조회하지 않는다.

    테스트 코드: RQ-010
    """
    use_cases = FakeUseCases()
    async with _client(use_cases, role=Role.USER) as http:
        # when: 컬럼이 없는 정의로 조회한다 (전제: 로그인한 user)
        await http.post(QUERY, json={"columns": []})

    # then: 조회 Port 호출이 없다
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
    """요청 모양이 틀리거나 모르는 키(예전 최상위 sort 포함)면 422 request-validation이다.

    테스트 코드: RQ-009
    """
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 모양이 틀린 본문으로 조회한다 (전제: 로그인한 user, 본문 매개변수)
        response = await http.post(QUERY, json=body_in)

    # then: 422 request-validation이다
    assert response.status_code == 422
    assert str(response.json()["type"]).endswith("request-validation")


async def test_timeout_returns_503_report_timeout_with_a_fixed_message() -> None:
    """시간 초과는 503 report-timeout과 고정 문구이고 내부 문구를 숨긴다.

    테스트 코드: RQ-061
    """
    use_cases = FakeUseCases()
    # given: 내부 문구가 든 시간 초과를 내는 조회 Port
    use_cases.uow.reports.error = ReportQueryTimeoutError("canceling statement: secret detail")
    async with _client(use_cases, role=Role.USER) as http:
        # when: 조회한다 (전제: 로그인한 user)
        response = await http.post(QUERY, json=VALID)

    # then: 503 report-timeout, 고정 문구이고 내부 문구가 응답에 없다
    assert response.status_code == 503
    body = response.json()
    assert str(body["type"]).endswith("report-timeout")
    assert body["title"] == "Report Timeout"
    assert body["detail"] == TIMEOUT_DETAIL
    assert "secret" not in response.text


# ---- 포맷·앞 N자·단위 ----


LEGACY_NUMBER_FORMATS = ["thousands", "krw_thousand", "krw_million", "decimal1", "percent_share"]


@pytest.mark.parametrize(
    ("field", "legacy"),
    [("deal.name", x) for x in ["as_is", "prefix", "name", "key"]]
    + [("deal.amount", x) for x in LEGACY_NUMBER_FORMATS]
    + [("deal.name", x) for x in LEGACY_NUMBER_FORMATS],
)
async def test_query_with_legacy_format_returns_invalid_report(field: str, legacy: str) -> None:
    """예전 포맷은 422 format-not-allowed이고 고정 문구다.

    테스트 코드: RQ-015
    """
    # given: 예전 포맷을 준 요청 (매개변수)
    body_in = {"columns": [{"field": field, "format": legacy}]}
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 조회한다 (전제: 로그인한 user)
        response = await http.post(QUERY, json=body_in)

    # then: invalid-report이고 위반은 format-not-allowed 하나와 고정 문구다
    assert response.status_code == 422
    body = response.json()
    assert str(body["type"]).endswith("invalid-report")
    assert [(e["location"], e["code"]) for e in body["errors"]] == [
        (["columns", 0, "format"], "format-not-allowed")
    ]
    assert body["errors"][0]["message"] == "이 필드는 포맷을 고를 수 없습니다"


CONVERTED_DATE_FIELDS = [
    "deal.last_updated_at",
    "deal.status_changed_at",
    "action.acted_at",
    "action.closed_at",
]


async def test_catalog_lists_the_converted_fields_as_dates_without_a_time_format() -> None:
    """카탈로그에서 key가 그대로인 네 필드는 date 형식이고 기본 ymd이며 ymd_hm이 없다.

    테스트 코드: RQ-113
    """
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 필드 목록을 요청한다 (전제: 로그인한 user)
        fields = {f["key"]: f for f in (await http.get(FIELDS)).json()["fields"]}

    # then: 네 필드는 date 형식, 기본 포맷 ymd, 포맷 선택지에 ymd_hm이 없다
    for key in CONVERTED_DATE_FIELDS:
        assert fields[key]["type"] == "date", key
        assert fields[key]["default_format"] == "ymd", key
        assert "ymd_hm" not in fields[key]["formats"], key
    # then: 시각(datetime) 형식은 등록일 하나뿐이고 ymd_hm을 가진다
    assert [k for k, f in fields.items() if f["type"] == "datetime"] == ["deal.created_at"]
    assert "ymd_hm" in fields["deal.created_at"]["formats"]


@pytest.mark.parametrize("field", CONVERTED_DATE_FIELDS)
async def test_query_with_ymd_hm_on_a_converted_field_returns_format_not_allowed(
    field: str,
) -> None:
    """네 날짜 필드에 ymd_hm을 요청하면 422 invalid-report의 format-not-allowed다.

    테스트 코드: RQ-114
    """
    # given: 네 필드(매개변수)에 ymd_hm을 준 요청
    body_in = {"columns": [{"field": field, "format": "ymd_hm"}]}
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 조회한다 (전제: 로그인한 user)
        response = await http.post(QUERY, json=body_in)

    # then: invalid-report이고 위반은 columns[0].format의 format-not-allowed 하나다
    assert response.status_code == 422
    body = response.json()
    assert str(body["type"]).endswith("invalid-report")
    assert [(e["location"], e["code"]) for e in body["errors"]] == [
        (["columns", 0, "format"], "format-not-allowed")
    ]


async def test_query_with_format_on_a_text_field_says_it_cannot_be_chosen() -> None:
    """텍스트 필드에 포맷을 주면 포맷을 고를 수 없다는 문구다.

    테스트 코드: RQ-014
    """
    # given: 텍스트 필드에 분기 포맷을 준 요청
    body_in = {"columns": [{"field": "deal.name", "format": "quarter"}]}
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 조회한다 (전제: 로그인한 user)
        body = (await http.post(QUERY, json=body_in)).json()

    # then: 문구가 포맷을 고를 수 없다는 안내다
    assert body["errors"][0]["message"] == "이 필드는 포맷을 고를 수 없습니다"


@pytest.mark.parametrize("length", [0, 201, "20", 1.5, True])
async def test_query_with_bad_prefix_length_returns_invalid_report(length: object) -> None:
    """범위 밖이거나 정수가 아닌 앞 N자는 422 value-invalid다.

    테스트 코드: RQ-016
    """
    # given: 잘못된 앞 N자를 준 요청 (매개변수)
    body_in = {"columns": [{"field": "deal.name", "prefix_length": length}]}
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 조회한다 (전제: 로그인한 user)
        response = await http.post(QUERY, json=body_in)

    # then: prefix_length 위치의 value-invalid 하나와 고정 문구다
    assert response.status_code == 422
    errors = response.json()["errors"]
    assert [(e["location"], e["code"]) for e in errors] == [
        (["columns", 0, "prefix_length"], "value-invalid")
    ]
    assert errors[0]["message"] == "앞 N자의 N은 1~200의 정수여야 합니다"


async def test_result_column_format_is_null_for_code_field_and_carries_prefix_length() -> None:
    """결과 열은 코드·텍스트·숫자 필드의 포맷이 null이고 앞 N자를 담는다.

    테스트 코드: RQ-062
    """
    # given: Status(앞 4자)·이름·금액(앞 200자) 컬럼의 요청
    body_in = {
        "columns": [
            {"field": "deal.status", "prefix_length": 4},
            {"field": "deal.name"},
            {"field": "deal.amount", "prefix_length": 200},
        ]
    }
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 조회한다 (전제: 로그인한 user)
        columns = (await http.post(QUERY, json=body_in)).json()["columns"]

    # then: 포맷은 모두 null이고 앞 N자는 4·None·200이다
    assert [(c["format"], c["prefix_length"]) for c in columns] == [
        (None, 4),
        (None, None),
        (None, 200),
    ]


async def test_catalog_formatless_fields() -> None:
    """텍스트·코드·사용자·숫자 필드는 포맷이 없고 포맷 어휘는 7개이며 묶음 포맷은 4개다.

    테스트 코드: RQ-003, RQ-007
    """
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 필드 목록을 요청한다 (전제: 로그인한 user)
        body = (await http.get(FIELDS)).json()

    # then: 해당 필드는 포맷 없음·기본값 null이고 포맷 어휘 7개, 묶음 포맷 4개다
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
    """필드는 40개이고 단위가 있는 필드는 금액 하나뿐이다.

    테스트 코드: RQ-002, RQ-004
    """
    async with _client(FakeUseCases(), role=Role.USER) as http:
        # when: 필드 목록을 요청한다 (전제: 로그인한 user)
        fields = (await http.get(FIELDS)).json()["fields"]

    # then: 모든 필드에 unit 키가 있고 값이 있는 것은 금액 krw뿐이며 필드는 40개다
    assert all("unit" in f for f in fields)
    assert {f["key"]: f["unit"] for f in fields if f["unit"] is not None} == {"deal.amount": "krw"}
    assert len(fields) == 40


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES])
async def test_admin_and_sales_also_receive_the_field_catalog(role: Role) -> None:
    """admin과 sales도 필드 카탈로그를 받는다.

    테스트 코드: RQ-001
    """
    # given: 로그인한 admin 또는 sales (매개변수)
    async with _client(FakeUseCases(), role=role) as http:
        # when: 필드 목록을 요청한다
        response = await http.get(FIELDS)

    # then: 200이고 필드 key 순서가 카탈로그와 같다
    assert response.status_code == 200, response.text
    assert [f["key"] for f in response.json()["fields"]] == [f.key for f in FIELD_CATALOG]
