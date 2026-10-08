"""전 구간 통합 테스트: HTTP → 라우터 → 유스케이스 → UnitOfWork → 실제 PostgreSQL(임시 DB).

실제로 commit하므로 테스트가 끝나면 테이블을 비운다.
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.container import Container
from app.main import create_app
from tests.e2e.conftest import make_settings
from tests.e2e.payloads import action_payload, customer_payload, deal_payload, partner_payload

CUSTOMERS = "/api/v1/customers"
PARTNERS = "/api/v1/partners"
DEALS = "/api/v1/deals"


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


@pytest.mark.integration
async def test_deal_search_filters_run_in_the_database(stack: AsyncClient) -> None:
    customer = (await stack.post(CUSTOMERS, json=customer_payload())).json()
    other = (await stack.post(CUSTOMERS, json=customer_payload(company_name="다른고객"))).json()
    partner = (await stack.post(PARTNERS, json=partner_payload())).json()
    rows = [
        ("D-1", customer["id"], partner["id"], "ERP 100% 구축", "2026-05-31"),
        ("D-2", customer["id"], None, "ERP 도입", "2026-06-01"),
        ("D-3", customer["id"], None, "ERP 확장", "2026-06-30"),
        ("D-4", other["id"], None, "ERP 보안", "2026-07-01"),
    ]
    for code, customer_id, partner_id, name, day in rows:
        body = deal_payload(
            customer_id, code=code, name=name, revenue_date=day, partner_id=partner_id
        )
        assert (await stack.post(DEALS, json=body)).status_code == 201
    deleted = (await stack.post(DEALS, json=deal_payload(customer["id"], code="D-5"))).json()
    assert (await stack.delete(f"{DEALS}/{deleted['id']}")).status_code == 204

    async def codes(**params: str) -> list[str]:
        response = await stack.get(DEALS, params=params)
        assert response.status_code == 200, response.text
        return [item["code"] for item in response.json()["items"]]

    assert await codes() == ["D-1", "D-2", "D-3", "D-4"]
    assert await codes(keyword="erp", customer_id=customer["id"]) == ["D-1", "D-2", "D-3"]
    assert await codes(keyword="100%") == ["D-1"]
    assert await codes(partner_id=partner["id"]) == ["D-1"]
    assert await codes(revenue_from="2026-06-01", revenue_to="2026-07-01") == ["D-2", "D-3"]
    assert await codes(owner="박영업", vendor="SAP", offset="1", limit="2") == ["D-2", "D-3"]
    assert await codes(owner="박영") == []


@pytest.mark.integration
async def test_sessions_live_in_the_database_and_logout_revokes_them(stack: AsyncClient) -> None:
    me = await stack.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "sales"

    assert (await stack.post("/api/v1/auth/logout")).status_code == 204

    assert (await stack.get("/api/v1/auth/me")).status_code == 401
    assert (await stack.get(CUSTOMERS)).status_code == 401


@pytest.mark.integration
async def test_stage_change_history_and_pipeline_run_in_the_database(stack: AsyncClient) -> None:
    customer = (await stack.post(CUSTOMERS, json=customer_payload())).json()
    deal = (await stack.post(DEALS, json=deal_payload(customer["id"]))).json()
    other = (
        await stack.post(
            DEALS,
            json=deal_payload(
                customer["id"], code="D-2", revenue_amount="0.0001", revenue_currency="USD"
            ),
        )
    ).json()
    assert deal["stage"] == "prospecting"

    first = await stack.post(f"{DEALS}/{deal['id']}/stage", json={"stage": "price_negotiation"})
    lost = await stack.post(
        f"{DEALS}/{deal['id']}/stage", json={"stage": "lost", "reason": "예산 삭감"}
    )
    blank_lost = await stack.post(f"{DEALS}/{other['id']}/stage", json={"stage": "lost"})
    same = await stack.post(f"{DEALS}/{deal['id']}/stage", json={"stage": "lost", "reason": "x"})
    await stack.post(f"{DEALS}/{other['id']}/stage", json={"stage": "lost", "reason": "경쟁"})

    assert (first.status_code, lost.status_code) == (200, 200)
    assert blank_lost.status_code == 422
    assert same.status_code == 409
    history = (await stack.get(f"{DEALS}/{deal['id']}/stage-changes")).json()["items"]
    assert [(h["from_stage"], h["to_stage"]) for h in history] == [
        ("price_negotiation", "lost"),
        ("prospecting", "price_negotiation"),
    ]
    assert history[0]["reason"] == "예산 삭감"
    assert history[0]["changed_by_subject"] == "dev-user"
    assert [
        d["code"] for d in (await stack.get(DEALS, params={"stage": "lost"})).json()["items"]
    ] == [
        "DEAL-001",
        "D-2",
    ]
    stages = {s["stage"]: s for s in (await stack.get(f"{DEALS}/pipeline")).json()["stages"]}
    assert stages["lost"]["deal_count"] == 2
    assert stages["lost"]["totals"] == [
        {"currency": "KRW", "amount": "150000000"},
        {"currency": "USD", "amount": "0.0001"},
    ]
    assert stages["prospecting"] == {"stage": "prospecting", "deal_count": 0, "totals": []}
    put = await stack.put(
        f"{DEALS}/{deal['id']}", json=deal_payload(customer["id"], name="이름 변경")
    )
    assert put.json()["stage"] == "lost"
    assert (await stack.delete(f"{DEALS}/{deal['id']}")).status_code == 204
    assert len((await stack.get(f"{DEALS}/{deal['id']}/stage-changes")).json()["items"]) == 2
    deleted_stages = {
        s["stage"]: s for s in (await stack.get(f"{DEALS}/pipeline")).json()["stages"]
    }
    assert deleted_stages["lost"]["deal_count"] == 1


@pytest.mark.integration
async def test_customer_and_partner_search_run_in_the_database(stack: AsyncClient) -> None:
    customers = [
        {"company_name": "Alpha 100% 상사", "phone": "031-777-4321"},
        {"company_name": "베타", "contact_title": "ALPHA 팀장"},
        {"company_name": "감마", "notes": "alpha 메모만"},
        {"company_name": "Alpha 삭제"},
    ]
    for body in customers:
        assert (await stack.post(CUSTOMERS, json=customer_payload(**body))).status_code == 201
    partners = [
        {"company_name": "Alpha 파트너", "email": "Search.Me@Sample.Example"},
        {"company_name": "델타", "contact_name": "알파"},
        {"company_name": "Alpha 삭제"},
    ]
    for body in partners:
        assert (await stack.post(PARTNERS, json=partner_payload(**body))).status_code == 201
    for base in (CUSTOMERS, PARTNERS):
        items = (await stack.get(base)).json()["items"]
        gone = next(i for i in items if i["company_name"] == "Alpha 삭제")
        assert (await stack.delete(f"{base}/{gone['id']}")).status_code == 204

    async def names(base: str, **params: str) -> list[str]:
        response = await stack.get(base, params=params)
        assert response.status_code == 200, response.text
        return [item["company_name"] for item in response.json()["items"]]

    assert await names(CUSTOMERS, keyword="alpha") == ["Alpha 100% 상사", "베타"]
    assert await names(CUSTOMERS, keyword="100%") == ["Alpha 100% 상사"]
    assert await names(CUSTOMERS, keyword="777-43") == ["Alpha 100% 상사"]
    assert await names(CUSTOMERS, keyword="alpha", offset="1", limit="1") == ["베타"]
    assert await names(PARTNERS, keyword="SEARCH.ME") == ["Alpha 파트너"]
    assert await names(PARTNERS, keyword="알파") == ["델타"]
    assert await names(PARTNERS, keyword="alpha") == ["Alpha 파트너"]
    assert await names(PARTNERS) == ["Alpha 파트너", "델타"]
