"""Dashboard 요약 라우터 (Dashboard AC-1·2·8): FakeUseCases 위의 HTTP 계약과 응답 모양.

DB 없이 라우터·스키마·오류 매핑·권한을 확인한다. 실제 DB를 지나는 시나리오는
functional(dashboard/)이 맡는다.
"""

import re
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories_auth import make_principal
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import CSRF_HEADER, make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
URL = "/api/v1/dashboard/summary"
ISO_WITH_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
COLUMN_KEYS = ["pipeline", "best", "most_likely", "commit", "won"]
STATUS_KEYS = [
    "prospecting",
    "introduction",
    "poc_preparation",
    "poc_completed",
    "technical_evaluation",
    "price_negotiation",
    "contract_completed",
]


@asynccontextmanager
async def _client(
    use_cases: FakeUseCases, *, role: Role | None = None
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    cookies = {}
    if role is not None:
        cookies[SESSION_COOKIE] = await use_cases.login_as(make_principal("root", role))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies=cookies,
    ) as http:
        yield http


def _seeded() -> FakeUseCases:
    from tests.fakes.catalog_seed import seed_catalog  # noqa: PLC0415

    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)
    return use_cases


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_can_read_the_summary(role: Role) -> None:
    async with _client(_seeded(), role=role) as http:
        response = await http.get(URL, params={"year": 2026})

    assert response.status_code == 200, response.text


async def test_anonymous_gets_401() -> None:
    async with _client(_seeded()) as http:
        response = await http.get(URL, params={"year": 2026})

    assert response.status_code == 401
    assert str(response.json()["type"]).endswith("unauthenticated")


async def test_response_has_the_documented_top_level_shape() -> None:
    async with _client(_seeded(), role=Role.USER) as http:
        body = (await http.get(URL, params={"year": 2026, "quarter": 4})).json()

    assert set(body) == {
        "as_of",
        "today",
        "period",
        "forecasts",
        "statuses",
        "quarters",
        "attention",
    }
    assert ISO_WITH_OFFSET.match(body["as_of"]), body["as_of"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", body["today"])
    assert body["period"] == {"year": 2026, "quarter": 4, "from": "2026-10-01", "to": "2026-12-31"}


async def test_a_year_only_period_has_a_null_quarter_and_the_whole_year() -> None:
    async with _client(_seeded(), role=Role.USER) as http:
        body = (await http.get(URL, params={"year": 2026})).json()

    assert body["period"] == {
        "year": 2026,
        "quarter": None,
        "from": "2026-01-01",
        "to": "2026-12-31",
    }


async def test_forecast_part_lists_columns_without_lost_and_cells_in_the_same_order() -> None:
    async with _client(_seeded(), role=Role.USER) as http:
        forecasts = (await http.get(URL, params={"year": 2026})).json()["forecasts"]

    assert set(forecasts) == {"columns", "cells", "open_total"}
    assert [c["key"] for c in forecasts["columns"]] == COLUMN_KEYS
    assert set(forecasts["columns"][0]) == {"key", "name", "outcome", "order"}
    assert [c["key"] for c in forecasts["cells"]] == COLUMN_KEYS
    assert all(set(c) == {"key", "count", "amount"} for c in forecasts["cells"])
    assert forecasts["open_total"] == {"count": 0, "amount": 0}


async def test_status_part_lists_every_status_with_zero_and_a_total() -> None:
    async with _client(_seeded(), role=Role.USER) as http:
        statuses = (await http.get(URL, params={"year": 2026})).json()["statuses"]

    assert set(statuses) == {"items", "total"}
    assert [i["key"] for i in statuses["items"]] == STATUS_KEYS
    assert all(set(i) == {"key", "name", "order", "count", "amount"} for i in statuses["items"])
    assert all((i["count"], i["amount"]) == (0, 0) for i in statuses["items"])
    assert statuses["total"] == {"count": 0, "amount": 0}


async def test_quarters_part_always_has_four_quarters_with_their_date_range() -> None:
    async with _client(_seeded(), role=Role.USER) as http:
        quarters = (await http.get(URL, params={"year": 2026, "quarter": 2})).json()["quarters"]

    assert [q["quarter"] for q in quarters] == [1, 2, 3, 4]
    assert [(q["from"], q["to"]) for q in quarters] == [
        ("2026-01-01", "2026-03-31"),
        ("2026-04-01", "2026-06-30"),
        ("2026-07-01", "2026-09-30"),
        ("2026-10-01", "2026-12-31"),
    ]
    for q in quarters:
        assert set(q) == {"quarter", "from", "to", "cells", "open_total", "total"}
        assert [c["key"] for c in q["cells"]] == COLUMN_KEYS
        assert q["open_total"] == {"count": 0, "amount": 0}
        assert q["total"] == {"count": 0, "amount": 0}


async def test_attention_part_has_the_documented_fields() -> None:
    async with _client(_seeded(), role=Role.USER) as http:
        attention = (await http.get(URL, params={"year": 2026})).json()["attention"]

    assert set(attention) == {
        "stale_days",
        "overdue",
        "stale",
        "closing_this_month",
        "closing_this_quarter",
    }
    assert attention["stale_days"] == 14
    assert (attention["overdue"], attention["stale"]) == (0, 0)
    assert set(attention["closing_this_month"]) == {"year", "month", "count"}
    assert set(attention["closing_this_quarter"]) == {"year", "quarter", "count"}


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"year": "abc"},
        {"year": 1899},
        {"year": 10000},
        {"year": 2026, "quarter": 0},
        {"year": 2026, "quarter": 5},
        {"year": 2026, "month": 3},
        {"year": 2026, "unknown": "x"},
        {"year": 2026, "owner_user_id": "abc"},
    ],
)
async def test_invalid_queries_are_request_validation_errors(params: dict[str, str | int]) -> None:
    async with _client(_seeded(), role=Role.ADMIN) as http:
        response = await http.get(URL, params=params)

    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")


async def test_the_openapi_declares_the_summary_path_as_get_only_with_four_params() -> None:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    spec = app.openapi()

    assert set(spec["paths"][URL]) == {"get"}
    names = {p["name"] for p in spec["paths"][URL]["get"]["parameters"]}
    assert names == {"year", "quarter", "owner_user_id", "vendor_id"}


async def test_the_openapi_declares_forecast_outcome_on_the_deal_list() -> None:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    spec = app.openapi()

    names = {p["name"] for p in spec["paths"]["/api/v1/deals"]["get"]["parameters"]}
    assert "forecast_outcome" in names
