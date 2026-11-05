"""Feature: Deal이 Won이 되면 라이선스 계약(미발급)이 자동으로 생긴다.

Deal 등록·폼 수정·목록 인라인 변경·Action 등록 어느 경로든 같은 규칙이다. 수동 '계약 추가'는
없다. 그 Deal에 계약이 이미 있으면(종료 포함) 새로 만들지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.license_contracts import (
    CONTRACTS,
    contracts_of,
    given_contract_of,
    given_open_deal,
    given_won_deal,
    then_contract_has_the_documented_keys,
    then_contract_row_count_is,
    then_contract_was_created_by_me,
    then_deal_reports_contract_count,
    then_statuses_are,
    when_end,
    when_enter_won_by_action,
    when_enter_won_by_change,
    when_enter_won_by_form,
    when_leave_won_by_change,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api


pytestmark = pytest.mark.integration


async def test_registering_a_won_deal_creates_a_not_issued_contract(api: Api) -> None:
    """Scenario: 처음부터 Won으로 등록한 Deal에 미발급 계약이 하나 생긴다."""
    # Given
    await given_logged_in_as(api)
    # When
    code = await given_won_deal(api)
    # Then
    contract = await given_contract_of(api, code)
    then_contract_has_the_documented_keys(contract)
    assert contract["status"] == "not_issued"
    assert (contract["license_start"], contract["license_end"], contract["term"]) == (
        None,
        None,
        None,
    )
    assert (contract["tech_owner"], contract["inspection_cycle"], contract["note"]) == (
        "",
        "none",
        "",
    )
    assert contract["renewed_from_id"] is None
    assert contract["ended_at"] is None
    assert contract["attachment_count"] == 0
    await then_contract_was_created_by_me(api, contract)
    await then_deal_reports_contract_count(api, code, 1)


async def test_registering_a_deal_that_is_not_won_creates_no_contract(api: Api) -> None:
    """Scenario: Won이 아닌 Deal에는 계약이 없다."""
    # Given
    await given_logged_in_as(api)
    # When
    code = await given_open_deal(api)
    # Then
    assert await contracts_of(api, code) == []
    await then_deal_reports_contract_count(api, code, 0)


async def test_forecast_won_by_an_inline_change_creates_a_contract(api: Api) -> None:
    """Scenario: 목록에서 Forecast를 Won으로 바꾸면 그 Deal의 미발급 계약 1건이 생긴다."""
    # Given
    await given_logged_in_as(api)
    code = await given_open_deal(api)
    # When
    response = await when_enter_won_by_change(api, code)
    # Then
    then_status_is(response, 200)
    contract = await given_contract_of(api, code)
    assert contract["status"] == "not_issued"
    assert contract["deal_code"] == code
    await then_contract_was_created_by_me(api, contract)
    await then_deal_reports_contract_count(api, code, 1)


async def test_won_through_the_deal_form_creates_a_contract(api: Api) -> None:
    """Scenario: Deal 폼에서 Status·Forecast를 Won으로 저장하면 계약이 생긴다."""
    # Given
    await given_logged_in_as(api)
    code = await given_open_deal(api)
    # When
    response = await when_enter_won_by_form(api, code)
    # Then
    then_status_is(response, 200)
    await then_statuses_are(api, code, ["not_issued"])


async def test_won_through_an_action_status_change_creates_a_contract(api: Api) -> None:
    """Scenario: Action을 등록하면서 Forecast를 Won으로 바꾸면 계약이 생긴다."""
    # Given
    await given_logged_in_as(api)
    code = await given_open_deal(api)
    # When
    response = await when_enter_won_by_action(api, code)
    # Then
    then_status_is(response, 201)
    await then_statuses_are(api, code, ["not_issued"])


async def test_leaving_and_reentering_won_keeps_the_single_contract(api: Api) -> None:
    """Scenario: Won -> 다른 상태(계약 유지) -> 다시 Won이어도 계약은 하나다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    first = await given_contract_of(api, code)
    then_status_is(await when_leave_won_by_change(api, code), 200)
    # When
    response = await when_enter_won_by_change(api, code)
    # Then
    then_status_is(response, 200)
    assert [c["id"] for c in await contracts_of(api, code)] == [first["id"]]
    await then_contract_row_count_is(api, code, 1)


async def test_reentering_won_with_only_an_ended_contract_adds_none(
    api: Api,
) -> None:
    """Scenario: 종료된 계약만 남아 있어도 다시 Won이 되면 새 계약을 만들지 않는다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    then_status_is(await when_end(api, contract["id"]), 200)
    then_status_is(await when_leave_won_by_change(api, code), 200)
    # When
    response = await when_enter_won_by_change(api, code)
    # Then
    then_status_is(response, 200)
    await then_statuses_are(api, code, ["ended"])


async def test_staying_won_with_other_edits_creates_no_second_contract(api: Api) -> None:
    """Scenario: Won인 채로 금액을 바꿔도 계약은 늘지 않는다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    # When
    response = await api.patch(f"/api/v1/deals/{code}", json={"revenue_amount": 777_000_000})
    # Then
    then_status_is(response, 200)
    await then_statuses_are(api, code, ["not_issued"])


async def test_there_is_no_manual_create_endpoint(api: Api) -> None:
    """Scenario: 계약을 직접 만드는 API는 없다(POST /license-contracts는 405)."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await api.post(CONTRACTS, json={})
    # Then
    then_status_is(response, 405)
