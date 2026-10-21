"""Forecast 스냅숏 라우터(P6 R2 AC-16·17): FakeUseCases 위의 HTTP 계약, 응답 모양, 오류 매핑.

DB 없이 라우터·스키마·오류 매핑·권한을 확인한다. 실제 DB를 지나는 시나리오는 functional(forecast/)이
맡는다. 스냅숏 저장소에 셀을 직접 넣어 두고 읽기 API만 호출한다(저장은 CLI의 일이다).
"""

import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.domain.forecast.snapshot import YearMonth
from app.main import create_app
from tests.factories_auth import make_principal, make_user
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import CSRF_HEADER, make_settings
from tests.unit.repositories.forecast_snapshot_case import (
    make_cell,
    make_column,
    make_snapshot,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
LIST_URL = "/api/v1/forecast/snapshots"
SUMMARY_URL = "/api/v1/forecast/snapshots/2026-09/summary"
ISO_WITH_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
TAKEN_AT = datetime(2026, 10, 1, 0, 5, tzinfo=UTC)
SEPT = YearMonth(2026, 9)


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


async def _seeded() -> tuple[FakeUseCases, int]:
    """기본 카탈로그와 담당자 kim, 2026-09 스냅숏(8월 pipeline 2건 140원 + won, Lost)을 둔다."""
    from tests.fakes.catalog_seed import seed_catalog  # noqa: PLC0415

    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)
    kim = make_user("kim", now=use_cases.clock.now())
    await use_cases.uow.users.add(kim)
    cells = [
        make_cell(kim.id, 2026, 8, "pipeline", count=2, amount=140),
        make_cell(kim.id, 2026, 8, "won", count=1, amount=500),
        make_cell(kim.id, 2026, 8, "lost", count=1, amount=999),
        make_cell(kim.id, 2026, 10, "pipeline", count=1, amount=3),
    ]
    columns = [make_column("pipeline", "초기"), make_column("won"), make_column("lost")]
    snapshot = make_snapshot(SEPT, *cells, taken_at=TAKEN_AT, columns=columns)
    await use_cases.uow.forecast_snapshots.replace(snapshot)
    return use_cases, int(kim.id)


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
@pytest.mark.parametrize("url", [LIST_URL, SUMMARY_URL])
async def test_every_role_can_read_the_snapshot_endpoints(role: Role, url: str) -> None:
    use_cases, _ = await _seeded()
    async with _client(use_cases, role=role) as http:
        response = await http.get(
            url, params={"year": 2026, "quarter": 3} if "summary" in url else None
        )

    assert response.status_code == 200, response.text


@pytest.mark.parametrize("url", [LIST_URL, SUMMARY_URL])
async def test_anonymous_gets_401(url: str) -> None:
    use_cases, _ = await _seeded()
    async with _client(use_cases) as http:
        response = await http.get(url, params={"year": 2026})

    assert response.status_code == 401
    assert str(response.json()["type"]).endswith("unauthenticated")


async def test_list_has_items_with_period_and_taken_at_newest_first() -> None:
    use_cases, _ = await _seeded()
    older = make_snapshot(
        YearMonth(2026, 8), taken_at=datetime(2026, 9, 1, 0, 5, tzinfo=UTC), columns=[]
    )
    await use_cases.uow.forecast_snapshots.replace(older)
    async with _client(use_cases, role=Role.USER) as http:
        body = (await http.get(LIST_URL)).json()

    assert set(body) == {"items"}
    assert [item["period"] for item in body["items"]] == ["2026-09", "2026-08"]
    assert all(set(item) == {"period", "taken_at"} for item in body["items"])
    assert all(ISO_WITH_OFFSET.match(item["taken_at"]) for item in body["items"])
    assert datetime.fromisoformat(body["items"][0]["taken_at"]) == TAKEN_AT


async def test_list_is_empty_without_snapshots() -> None:
    async with _client(FakeUseCases(), role=Role.USER) as http:
        body = (await http.get(LIST_URL)).json()

    assert body == {"items": []}


async def test_snapshot_summary_has_the_live_shape_with_snapshot_basis() -> None:
    use_cases, kim = await _seeded()
    async with _client(use_cases, role=Role.USER) as http:
        body = (await http.get(SUMMARY_URL, params={"year": 2026, "quarter": 3})).json()

    assert set(body) == {"basis", "as_of", "snapshot_period", "period", "columns", "rows", "total"}
    assert body["basis"] == "snapshot"
    assert body["snapshot_period"] == "2026-09"
    assert ISO_WITH_OFFSET.match(body["as_of"]), body["as_of"]
    assert datetime.fromisoformat(body["as_of"]) == TAKEN_AT
    assert body["period"] == {
        "year": 2026,
        "quarter": 3,
        "month": None,
        "from": "2026-07-01",
        "to": "2026-09-30",
    }
    assert [c["key"] for c in body["columns"]] == ["pipeline", "won"]
    assert body["columns"][0]["name"] == "초기"  # 스냅숏 당시 이름
    assert [r["owner"]["id"] for r in body["rows"]] == [kim]


async def test_snapshot_summary_cells_follow_the_columns_and_leave_out_lost() -> None:
    use_cases, _ = await _seeded()
    async with _client(use_cases, role=Role.USER) as http:
        body = (await http.get(SUMMARY_URL, params={"year": 2026, "quarter": 3})).json()

    row = body["rows"][0]
    assert [c["key"] for c in row["cells"]] == ["pipeline", "won"]
    assert [(c["count"], c["amount"]) for c in row["cells"]] == [(2, 140), (1, 500)]
    assert row["open_total"] == {"count": 2, "amount": 140}
    assert body["total"]["owner"] is None
    assert body["total"]["open_total"] == {"count": 2, "amount": 140}


async def test_snapshot_summary_period_filters_the_stored_months() -> None:
    use_cases, _ = await _seeded()
    async with _client(use_cases, role=Role.USER) as http:
        q4 = (await http.get(SUMMARY_URL, params={"year": 2026, "quarter": 4})).json()
        august = (await http.get(SUMMARY_URL, params={"year": 2026, "month": 8})).json()

    assert q4["total"]["open_total"] == {"count": 1, "amount": 3}
    assert august["total"]["open_total"] == {"count": 2, "amount": 140}
    assert august["period"]["month"] == 8


async def test_snapshot_summary_owner_filter() -> None:
    use_cases, kim = await _seeded()
    async with _client(use_cases, role=Role.USER) as http:
        mine = (await http.get(SUMMARY_URL, params={"year": 2026, "owner_user_id": kim})).json()
        other = (
            await http.get(SUMMARY_URL, params={"year": 2026, "owner_user_id": kim + 1})
        ).json()

    assert [r["owner"]["id"] for r in mine["rows"]] == [kim]
    assert other["rows"] == []


@pytest.mark.parametrize("period", ["2026-08", "2027-01", "2026-9", "abc", "2026-13", "2026-00"])
async def test_missing_or_malformed_period_is_404_not_found(period: str) -> None:
    use_cases, _ = await _seeded()
    async with _client(use_cases, role=Role.ADMIN) as http:
        response = await http.get(
            f"/api/v1/forecast/snapshots/{period}/summary", params={"year": 2026}
        )

    assert response.status_code == 404, response.text
    assert str(response.json()["type"]).endswith("not-found")


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"year": "abc"},
        {"year": 1899},
        {"year": 2026, "quarter": 5},
        {"year": 2026, "month": 13},
        {"year": 2026, "vendor_id": 1},
        {"year": 2026, "unknown": "x"},
    ],
)
async def test_invalid_snapshot_queries_are_request_validation_errors(
    params: dict[str, str | int],
) -> None:
    use_cases, _ = await _seeded()
    async with _client(use_cases, role=Role.ADMIN) as http:
        response = await http.get(SUMMARY_URL, params=params)

    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")


async def test_quarter_with_month_is_an_invalid_value_problem() -> None:
    use_cases, _ = await _seeded()
    async with _client(use_cases, role=Role.ADMIN) as http:
        response = await http.get(SUMMARY_URL, params={"year": 2026, "quarter": 1, "month": 1})

    assert response.status_code == 422, response.text
    body = response.json()
    assert str(body["type"]).endswith("invalid-value")
    assert body["detail"] == "Quarter와 월은 함께 선택할 수 없습니다."


async def test_the_openapi_declares_the_snapshot_paths_as_get_only() -> None:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    spec = app.openapi()

    summary_path = "/api/v1/forecast/snapshots/{period}/summary"
    assert set(spec["paths"][LIST_URL]) == {"get"}
    assert set(spec["paths"][summary_path]) == {"get"}
    names = {p["name"] for p in spec["paths"][summary_path]["get"]["parameters"]}
    assert names == {"period", "year", "quarter", "month", "owner_user_id"}
