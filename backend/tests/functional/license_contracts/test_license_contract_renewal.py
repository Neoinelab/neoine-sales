"""Feature: 발급 상태 계약을 갱신하면 같은 Deal에 새 계약이 생기고 이전 계약은 종료된다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.license_contracts import (
    ISSUED_ONLY,
    contract_url,
    contracts_of,
    given_contract_file,
    given_contract_of,
    given_issued_contract,
    given_won_deal,
    then_contract_has_the_documented_keys,
    then_deal_reports_contract_count,
    when_end,
    when_get_contract,
    when_renew,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_renewing_creates_a_renewal_row_and_ends_the_previous_one(api: Api) -> None:
    """Scenario: 갱신하면 새 행(발급(갱신), 갱신 원본 id)이 생기고 이전 행은 종료다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    previous = await given_issued_contract(api, code, start="2026-01-01")
    # When
    response = await when_renew(
        api, previous["id"], start="2027-01-01", amount=2, unit="year", tech_owner="새 담당"
    )
    # Then
    then_status_is(response, 201)
    renewal = response.json()
    then_contract_has_the_documented_keys(renewal)
    assert response.headers["location"].endswith(contract_url(renewal["id"]))
    assert renewal["id"] != previous["id"]
    assert renewal["deal_code"] == code
    assert renewal["status"] == "issued_renewal"
    assert renewal["renewed_from_id"] == previous["id"]
    assert (renewal["license_start"], renewal["license_end"]) == ("2027-01-01", "2028-12-31")
    assert renewal["tech_owner"] == "새 담당"
    ended = (await when_get_contract(api, previous["id"])).json()
    assert ended["status"] == "ended"
    assert ended["ended_at"] is not None
    assert (ended["license_start"], ended["license_end"]) == ("2026-01-01", "2026-12-31")
    assert [c["status"] for c in await contracts_of(api, code)] == ["ended", "issued_renewal"]
    await then_deal_reports_contract_count(api, code, 2)


async def test_after_renewing_the_deal_has_exactly_one_issued_contract(api: Api) -> None:
    """Scenario: 갱신을 거듭해도 발급 상태 계약은 항상 하나다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    first = await given_issued_contract(api, code)
    second = (await when_renew(api, first["id"], start="2027-01-01")).json()
    # When
    response = await when_renew(api, second["id"], start="2028-01-01")
    # Then
    then_status_is(response, 201)
    statuses = [c["status"] for c in await contracts_of(api, code)]
    assert statuses == ["ended", "ended", "issued_renewal"]


async def test_attachments_stay_with_the_previous_contract(api: Api) -> None:
    """Scenario: 갱신해도 첨부는 이전 계약에 남고 새 계약은 비어 있다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    previous = await given_issued_contract(api, code)
    await given_contract_file(api, previous["id"], name="old.pdf")
    # When
    response = await when_renew(api, previous["id"], start="2027-01-01")
    # Then
    then_status_is(response, 201)
    assert response.json()["attachment_count"] == 0
    assert (await when_get_contract(api, previous["id"])).json()["attachment_count"] == 1


@pytest.mark.parametrize("which", ["not_issued", "ended"])
async def test_only_an_issued_contract_can_be_renewed(api: Api, which: str) -> None:
    """Scenario: 미발급·종료 계약의 갱신은 409(발급 상태 계약만 갱신할 수 있습니다)다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    if which == "ended":
        then_status_is(await when_end(api, contract["id"]), 200)
    # When
    response = await when_renew(api, contract["id"])
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == ISSUED_ONLY
    assert len(await contracts_of(api, code)) == 1


@pytest.mark.parametrize("overrides", [{"amount": 0}, {"amount": 100}, {"unit": "week"}])
async def test_an_invalid_renewal_period_changes_nothing(
    api: Api, overrides: dict[str, object]
) -> None:
    """Scenario: 갱신 기간이 틀리면 422이고 이전 계약은 발급 상태 그대로, 새 행도 없다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    previous = await given_issued_contract(api, code)
    # When
    response = await when_renew(api, previous["id"], **overrides)  # type: ignore[arg-type]
    # Then
    assert response.status_code == 422, response.text
    assert [c["status"] for c in await contracts_of(api, code)] == ["issued_new"]
