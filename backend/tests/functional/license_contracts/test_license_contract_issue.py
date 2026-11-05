"""Feature: 미발급 계약을 발급하면 종료일이 서버에서 계산되고 한 Deal의 발급 상태는 하나뿐이다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.license_contracts import (
    ALREADY_ISSUED,
    DEAL_NOT_WON,
    NOT_ISSUED_ONLY,
    contracts_of,
    given_contract_of,
    given_extra_contract_row,
    given_issued_contract,
    given_won_deal,
    then_contract_has_the_documented_keys,
    then_statuses_are,
    when_end,
    when_enter_won_by_change,
    when_get_contract,
    when_issue,
    when_leave_won_by_change,
    when_renew,
    when_update_contract,
)
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_issuing_stores_the_period_and_the_computed_end_date(api: Api) -> None:
    """Scenario: 미발급 계약을 발급하면 발급(신규)이 되고 종료일은 시작일 + 기간 - 1일이다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    # When
    response = await when_issue(
        api, contract["id"], start="2026-01-01", amount=1, unit="year", tech_owner="이기술"
    )
    # Then
    then_status_is(response, 200)
    issued = response.json()
    then_contract_has_the_documented_keys(issued)
    assert issued["id"] == contract["id"]
    assert issued["status"] == "issued_new"
    assert (issued["license_start"], issued["license_end"]) == ("2026-01-01", "2026-12-31")
    assert issued["term"] == {"amount": 1, "unit": "year"}
    assert issued["tech_owner"] == "이기술"
    reread = (await when_get_contract(api, contract["id"])).json()
    assert reread == issued


@pytest.mark.parametrize(
    ("start", "amount", "unit", "end"),
    [
        ("2026-01-31", 1, "month", "2026-02-28"),
        ("2026-03-15", 1, "month", "2026-04-14"),
        ("2026-11-15", 3, "month", "2027-02-14"),
        ("2026-01-01", 6, "month", "2026-06-30"),
        ("2026-01-01", 2, "year", "2027-12-31"),
        ("2028-02-29", 1, "year", "2029-02-28"),
    ],
)
async def test_the_end_date_follows_the_period_rule(
    api: Api, start: str, amount: int, unit: str, end: str
) -> None:
    """Scenario: 종료일 계산이 프런트 미리보기와 같은 규칙이다(월 말 보정 포함)."""
    # Given
    await given_logged_in_as(api)
    contract = await given_contract_of(api, await given_won_deal(api))
    # When
    response = await when_issue(api, contract["id"], start=start, amount=amount, unit=unit)
    # Then
    then_status_is(response, 200)
    assert response.json()["license_end"] == end


async def test_a_second_issue_in_the_same_deal_is_rejected(api: Api) -> None:
    """Scenario: 이미 발급 상태 계약이 있는 Deal의 다른 미발급 계약은 발급할 수 없다(409)."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    await given_issued_contract(api, code)
    waiting = await given_extra_contract_row(api, code)
    # When
    response = await when_issue(api, waiting["id"], start="2027-01-01")
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == ALREADY_ISSUED
    assert (await when_get_contract(api, waiting["id"])).json()["status"] == "not_issued"


async def test_issuing_an_issued_contract_is_rejected_with_the_transition_message(
    api: Api,
) -> None:
    """Scenario: 발급 상태 계약을 다시 발급하면 409(미발급 계약만 발급할 수 있습니다)."""
    # Given
    await given_logged_in_as(api)
    issued = await given_issued_contract(api, await given_won_deal(api))
    # When
    response = await when_issue(api, issued["id"], start="2027-01-01")
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == NOT_ISSUED_ONLY
    reread = (await when_get_contract(api, issued["id"])).json()
    assert reread["license_start"] == "2026-01-01"


async def test_issuing_an_ended_contract_is_rejected(api: Api) -> None:
    """Scenario: 종료된 계약은 발급할 수 없다(409)."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    then_status_is(await when_end(api, contract["id"]), 200)
    # When
    response = await when_issue(api, contract["id"])
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == NOT_ISSUED_ONLY


async def test_another_deal_may_issue_its_own_contract(api: Api) -> None:
    """Scenario: 발급 상태 제한은 Deal 단위라 다른 Deal의 계약은 발급할 수 있다."""
    # Given
    await given_logged_in_as(api)
    await given_issued_contract(api, await given_won_deal(api))
    other = await given_contract_of(api, await given_won_deal(api, name="다른 Deal"))
    # When
    response = await when_issue(api, other["id"])
    # Then
    then_status_is(response, 200)
    assert response.json()["status"] == "issued_new"


async def test_issuing_after_ending_the_issued_one_is_allowed(api: Api) -> None:
    """Scenario: 발급 계약을 종료하면 같은 Deal의 다른 계약을 발급할 수 있다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    first = await given_issued_contract(api, code)
    waiting = await given_extra_contract_row(api, code)
    then_status_is(await when_end(api, first["id"]), 200)
    # When
    response = await when_issue(api, waiting["id"], start="2027-01-01")
    # Then
    then_status_is(response, 200)
    statuses = sorted(c["status"] for c in await contracts_of(api, code))
    assert statuses == ["ended", "issued_new"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": 0},
        {"amount": 100},
        {"unit": "week"},
        {"start": "2026-13-01"},
        {"start": "1899-12-31"},
    ],
)
async def test_an_invalid_period_is_rejected_and_nothing_changes(
    api: Api, overrides: dict[str, object]
) -> None:
    """Scenario: 기간 값이 틀리면 422이고 계약은 미발급 그대로다."""
    # Given
    await given_logged_in_as(api)
    contract = await given_contract_of(api, await given_won_deal(api))
    # When
    response = await when_issue(api, contract["id"], **overrides)  # type: ignore[arg-type]
    # Then
    assert response.status_code == 422, response.text
    assert (await when_get_contract(api, contract["id"])).json()["status"] == "not_issued"


async def test_the_end_date_cannot_be_sent(api: Api) -> None:
    """Scenario: 종료일은 서버가 계산하므로 요청에 보내면 422(request-validation)다."""
    # Given
    await given_logged_in_as(api)
    contract = await given_contract_of(api, await given_won_deal(api))
    body = {"start_date": "2026-01-01", "term_amount": 1, "term_unit": "year"}
    # When
    response = await api.post(
        f"/api/v1/license-contracts/{contract['id']}/issue", json={**body, "end_date": "2026-12-31"}
    )
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_issuing_a_missing_contract_is_404(api: Api) -> None:
    """Scenario: 없는 계약을 발급하면 404다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_issue(api, MISSING_ID)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


async def test_issuing_on_a_deal_that_left_won_is_rejected(api: Api) -> None:
    """Scenario: Won에서 '유지'로 벗어난 Deal의 미발급 계약은 발급할 수 없다(409)."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    then_status_is(await when_leave_won_by_change(api, code, delete=False), 200)
    # When
    response = await when_issue(api, contract["id"])
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == DEAL_NOT_WON
    reread = (await when_get_contract(api, contract["id"])).json()
    assert (reread["status"], reread["license_start"]) == ("not_issued", None)


async def test_renewing_on_a_deal_that_left_won_is_rejected(api: Api) -> None:
    """Scenario: Won이 아닌 Deal의 계약 갱신은 계약 상태보다 먼저 Won 아님으로 409다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    then_status_is(await when_leave_won_by_change(api, code, delete=False), 200)
    # When
    response = await when_renew(api, contract["id"])
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == DEAL_NOT_WON
    await then_statuses_are(api, code, ["not_issued"])


async def test_fields_and_end_still_work_for_a_deal_that_left_won(api: Api) -> None:
    """Scenario: Won이 아닌 Deal의 계약도 계약 칸 수정과 종료는 할 수 있다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    then_status_is(await when_leave_won_by_change(api, code, delete=False), 200)
    # When
    updated = await when_update_contract(api, contract["id"], note="메모")
    ended = await when_end(api, contract["id"])
    # Then
    then_status_is(updated, 200)
    then_status_is(ended, 200)
    assert ended.json()["status"] == "ended"


async def test_issuing_works_again_once_the_deal_is_won_again(api: Api) -> None:
    """Scenario: 다시 Won이 된 Deal의 계약은 발급할 수 있다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    then_status_is(await when_leave_won_by_change(api, code, delete=False), 200)
    then_status_is(await when_enter_won_by_change(api, code), 200)
    # When
    response = await when_issue(api, contract["id"])
    # Then
    then_status_is(response, 200)
    assert response.json()["status"] == "issued_new"
