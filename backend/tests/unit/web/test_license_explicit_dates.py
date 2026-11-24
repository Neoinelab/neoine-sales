import pytest

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.license_contract_http import BASE, WON_DEAL, clients, seed_contract


@pytest.mark.parametrize("end", ["2026-01-31", "2026-03-17"])
async def test_issue_stores_the_selected_end_date(end: str) -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, deal_overrides=WON_DEAL)
    async with clients(use_cases, {"kim": Role.SALES}) as client:
        response = await client["kim"].post(
            f"{BASE}/{contract.id}/issue",
            json={"start_date": "2026-01-31", "end_date": end},
        )
        assert response.status_code == 200
        stored = (await client["kim"].get(f"{BASE}/{contract.id}")).json()
        assert (stored["license_start"], stored["license_end"], stored["term"]) == (
            "2026-01-31",
            end,
            None,
        )


@pytest.mark.parametrize("end", [None, "2026-01-30", "2026-02-30", "3000-01-01"])
async def test_issue_rejects_missing_invalid_or_reversed_end_date(end: str | None) -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, deal_overrides=WON_DEAL)
    async with clients(use_cases, {"kim": Role.SALES}) as client:
        response = await client["kim"].post(
            f"{BASE}/{contract.id}/issue",
            json={"start_date": "2026-01-31", "end_date": end},
        )
        assert response.status_code == 422
        stored = (await client["kim"].get(f"{BASE}/{contract.id}")).json()
        assert stored["status"] == "not_issued"
