"""Forecast 요약 라우터(P6 R1 AC-1·2·8·9): FakeUseCases 위의 HTTP 계약, 응답 모양, 판정 순서.

DB 없이 라우터·스키마·오류 매핑·권한을 확인한다. 실제 DB를 지나는 시나리오는 functional(forecast/)이
맡는다.
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
URL = "/api/v1/forecast/summary"
ISO_WITH_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
COLUMN_KEYS = ["pipeline", "best", "most_likely", "commit", "won"]


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


async def test_response_has_the_documented_shape() -> None:
    async with _client(_seeded(), role=Role.USER) as http:
        body = (await http.get(URL, params={"year": 2026, "quarter": 4})).json()

    assert set(body) == {"basis", "as_of", "snapshot_period", "period", "columns", "rows", "total"}
    assert body["basis"] == "live"
    assert body["snapshot_period"] is None
    assert ISO_WITH_OFFSET.match(body["as_of"]), body["as_of"]
    assert body["period"] == {
        "year": 2026,
        "quarter": 4,
        "month": None,
        "from": "2026-10-01",
        "to": "2026-12-31",
    }
    assert [c["key"] for c in body["columns"]] == COLUMN_KEYS
    assert set(body["columns"][0]) == {"key", "name", "outcome", "order"}
    assert [c["outcome"] for c in body["columns"]][-1] == "won"
    assert body["rows"] == []


async def test_total_cells_follow_the_columns_as_a_list() -> None:
    async with _client(_seeded(), role=Role.USER) as http:
        body = (await http.get(URL, params={"year": 2026})).json()

    total = body["total"]
    assert total["owner"] is None
    assert [cell["key"] for cell in total["cells"]] == COLUMN_KEYS
    assert all(set(cell) == {"key", "count", "amount"} for cell in total["cells"])
    assert total["open_total"] == {"count": 0, "amount": 0}


async def test_month_period_has_the_month_range() -> None:
    async with _client(_seeded(), role=Role.USER) as http:
        body = (await http.get(URL, params={"year": 2028, "month": 2})).json()

    assert body["period"]["from"] == "2028-02-01"
    assert body["period"]["to"] == "2028-02-29"
    assert body["period"]["quarter"] is None


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"year": "abc"},
        {"year": 1899},
        {"year": 10000},
        {"year": 2026, "quarter": 0},
        {"year": 2026, "quarter": 5},
        {"year": 2026, "month": 0},
        {"year": 2026, "month": 13},
        {"year": 2026, "unknown": "x"},
        {"year": 2026, "owner_user_id": "abc"},
    ],
)
async def test_invalid_queries_are_request_validation_errors(params: dict[str, str | int]) -> None:
    async with _client(_seeded(), role=Role.ADMIN) as http:
        response = await http.get(URL, params=params)

    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")


async def test_quarter_with_month_is_an_invalid_value_problem() -> None:
    async with _client(_seeded(), role=Role.ADMIN) as http:
        response = await http.get(URL, params={"year": 2026, "quarter": 1, "month": 1})

    assert response.status_code == 422, response.text
    body = response.json()
    assert str(body["type"]).endswith("invalid-value")
    assert body["detail"] == "Quarter와 월은 함께 선택할 수 없습니다."


async def test_the_openapi_declares_the_summary_path_as_get_only() -> None:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    spec = app.openapi()

    assert set(spec["paths"][URL]) == {"get"}
    names = {p["name"] for p in spec["paths"][URL]["get"]["parameters"]}
    assert names == {"year", "quarter", "month", "owner_user_id", "vendor_id"}
