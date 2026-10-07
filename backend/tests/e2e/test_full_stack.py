"""전 구간 통합 테스트: HTTP → 라우터 → 유스케이스 → UnitOfWork → 실제 PostgreSQL(임시 DB).

실제로 commit하므로 테스트가 끝나면 테이블을 비운다.
"""

import asyncio
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.container import Container
from app.main import create_app
from tests.e2e.conftest import make_settings
from tests.e2e.payloads import action_payload, customer_payload, deal_payload, partner_payload

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL

CUSTOMERS = "/api/v1/customers"
PARTNERS = "/api/v1/partners"
DEALS = "/api/v1/deals"


@pytest_asyncio.fixture
async def stack(test_database_url: URL) -> AsyncIterator[AsyncClient]:
    settings = make_settings(database_url=test_database_url.render_as_string(hide_password=False))
    container = Container(settings)
    app = create_app(settings=settings, use_cases=container)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield http
    finally:
        await container.dispose()
        engine = create_async_engine(test_database_url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("truncate deal_actions, deals, customers, partners cascade")
                )
        finally:
            await engine.dispose()


@pytest.mark.integration
async def test_customer_partner_and_deal_lifecycle_over_http(stack: AsyncClient) -> None:
    customer = (await stack.post(CUSTOMERS, json=customer_payload())).json()
    partner = (await stack.post(PARTNERS, json=partner_payload())).json()

    created = await stack.post(
        DEALS,
        json=deal_payload(
            customer["id"],
            partner_id=partner["id"],
            revenue_amount="1234567.8912",
            revenue_currency="USD",
        ),
    )
    assert created.status_code == 201
    deal = created.json()

    fetched = (await stack.get(f"{DEALS}/{deal['id']}")).json()
    assert fetched == deal
    assert fetched["revenue_amount"] == "1234567.8912"
    assert fetched["partner_id"] == partner["id"]
    assert (await stack.get(f"{DEALS}/by-code/deal-001")).json() == deal

    updated = await stack.put(
        f"{DEALS}/{deal['id']}",
        json=deal_payload(customer["id"], name="확장 프로젝트", revenue_amount="200"),
    )
    assert updated.status_code == 200
    assert updated.json()["partner_id"] is None  # 전체 교체
    assert (await stack.get(f"{DEALS}/{deal['id']}")).json()["name"] == "확장 프로젝트"

    assert (await stack.delete(f"{DEALS}/{deal['id']}")).status_code == 204
    assert (await stack.get(f"{DEALS}/{deal['id']}")).status_code == 404
    assert (await stack.get(DEALS)).json()["items"] == []


@pytest.mark.integration
async def test_database_rules_surface_as_problem_responses(stack: AsyncClient) -> None:
    customer = (await stack.post(CUSTOMERS, json=customer_payload())).json()
    await stack.post(DEALS, json=deal_payload(customer["id"]))

    duplicate = await stack.post(DEALS, json=deal_payload(customer["id"], code="DEAL-001"))
    unknown_customer = await stack.post(
        DEALS, json=deal_payload("00000000-0000-4000-8000-000000000000", code="OTHER")
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["type"].endswith("already-exists")
    assert unknown_customer.status_code == 422
    assert unknown_customer.json()["type"].endswith("invalid-reference")
    assert len((await stack.get(DEALS)).json()["items"]) == 1


@pytest.mark.integration
async def test_deleted_customer_cannot_receive_new_deals(stack: AsyncClient) -> None:
    customer = (await stack.post(CUSTOMERS, json=customer_payload())).json()
    await stack.delete(f"{CUSTOMERS}/{customer['id']}")

    response = await stack.post(DEALS, json=deal_payload(customer["id"]))

    assert response.status_code == 422
    assert response.json()["type"].endswith("invalid-reference")


@pytest.mark.integration
async def test_concurrent_requests_do_not_share_transaction_state(stack: AsyncClient) -> None:
    responses = await asyncio.gather(
        *(stack.post(CUSTOMERS, json=customer_payload(company_name=f"동시{n}")) for n in range(8))
    )

    assert {r.status_code for r in responses} == {201}
    assert len({r.json()["id"] for r in responses}) == 8
    listed = (await stack.get(CUSTOMERS, params={"limit": 50})).json()["items"]
    assert sorted(item["company_name"] for item in listed) == sorted(f"동시{n}" for n in range(8))


@pytest.mark.integration
async def test_readiness_checks_the_real_database(stack: AsyncClient) -> None:
    response = await stack.get("/readyz")

    assert response.status_code == 200


async def test_readiness_is_503_when_the_database_is_unreachable() -> None:
    settings = make_settings(database_url="postgresql+asyncpg://user:pw@127.0.0.1:1/none")
    container = Container(settings)
    app = create_app(settings=settings, use_cases=container)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            response = await http.get("/readyz")
    finally:
        await container.dispose()

    assert response.status_code == 503
    assert "pw" not in response.text


@pytest.mark.integration
async def test_deal_history_is_recorded_and_searched_in_the_database(stack: AsyncClient) -> None:
    customer = (await stack.post(CUSTOMERS, json=customer_payload())).json()
    deal = (await stack.post(DEALS, json=deal_payload(customer["id"]))).json()
    for title, content, when in [
        ("첫 통화", "할인율 100% 요청", "2026-03-01T10:00:00+09:00"),
        ("제안서 발송", "견적 첨부", "2026-03-05T10:00:00+09:00"),
    ]:
        body = action_payload(title=title, content=content, acted_at=when)
        assert (await stack.post(f"{DEALS}/{deal['id']}/actions", json=body)).status_code == 201

    everything = (await stack.get(f"{DEALS}/{deal['id']}/actions")).json()["items"]
    literal = (await stack.get("/api/v1/deal-actions", params={"keyword": "100%"})).json()["items"]
    ranged = (
        await stack.get("/api/v1/deal-actions", params={"acted_from": "2026-03-02T00:00:00+09:00"})
    ).json()["items"]

    assert [a["title"] for a in everything] == ["제안서 발송", "첫 통화"]  # 최신순
    assert [a["title"] for a in literal] == ["첫 통화"]
    assert [a["title"] for a in ranged] == ["제안서 발송"]
    assert (await stack.delete(f"{DEALS}/{deal['id']}")).status_code == 204
    assert len((await stack.get(f"{DEALS}/{deal['id']}/actions")).json()["items"]) == 2
