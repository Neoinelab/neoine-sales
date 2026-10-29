"""Deal 삭제 영향 응답의 partner_meeting_count(AC18): 필수 필드이고 그 Deal의 미팅 건수다."""

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.partner_meeting_http import clients, item, seed_deals

IMPACT_KEYS = {"history_count", "action_count", "attachment_count", "partner_meeting_count"}


async def test_the_deletion_impact_counts_the_partner_meetings_of_that_deal() -> None:
    use_cases = FakeUseCases()
    erp, mes = await seed_deals(use_cases, "ERP", "MES")
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        await c["kim"].post(
            "/api/v1/partner-meetings", json={"items": [item(erp), item(erp), item(mes)]}
        )
        first = await c["kim"].get(f"/api/v1/deals/{erp}/deletion-impact")
        second = await c["kim"].get(f"/api/v1/deals/{mes}/deletion-impact")

    assert first.status_code == 200, first.text
    assert set(first.json()) == IMPACT_KEYS
    assert first.json()["partner_meeting_count"] == 2
    assert second.json()["partner_meeting_count"] == 1


async def test_a_deal_without_meetings_has_a_zero_count() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].get(f"/api/v1/deals/{erp}/deletion-impact")

    assert response.json()["partner_meeting_count"] == 0
