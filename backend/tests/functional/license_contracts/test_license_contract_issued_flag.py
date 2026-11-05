"""Feature: Deal 응답은 발급 계약 유무(has_issued_license_contract)를, 계약 응답은 Deal의 Won 여부
(deal_is_won)를 알려 준다. 화면이 Won 이탈·발급 버튼을 요청 전에 막는 데 쓴다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deals import DEALS
from tests.functional.steps.license_contracts import (
    given_contract_of,
    given_issued_contract,
    given_open_deal,
    given_won_deal,
    when_delete_contract,
    when_end,
    when_get_contract,
    when_leave_won_by_change,
    when_renew,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _flag(api: Api, code: str) -> tuple[bool, bool]:
    """(상세 응답, 목록 행)의 has_issued_license_contract."""
    detail = (await api.get(f"{DEALS}/{code}")).json()
    page = (await api.get(DEALS, params={"limit": 200})).json()
    (row,) = [r for r in page["items"] if r["code"] == code]
    return detail["has_issued_license_contract"], row["has_issued_license_contract"]


async def test_the_flag_is_false_until_a_contract_is_issued(api: Api) -> None:
    """Scenario: 미발급 계약만 있거나 계약이 없으면 false다."""
    # Given
    await given_logged_in_as(api)
    won = await given_won_deal(api)
    open_code = await given_open_deal(api)
    # When / Then
    assert await _flag(api, won) == (False, False)
    assert await _flag(api, open_code) == (False, False)


async def test_the_flag_follows_issue_renewal_and_end(api: Api) -> None:
    """Scenario: 발급하면 true, 갱신 뒤 새 발급 행이 있으면 true, 그 행을 종료하면 false다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_issued_contract(api, code)
    # When / Then
    assert await _flag(api, code) == (True, True)
    renewal = (await when_renew(api, contract["id"])).json()
    assert await _flag(api, code) == (True, True)
    then_status_is(await when_end(api, renewal["id"]), 200)
    assert await _flag(api, code) == (False, False)


async def test_the_flag_turns_false_when_the_admin_deletes_the_issued_contract(api: Api) -> None:
    """Scenario: 발급 계약을 admin이 삭제하면 false가 된다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_issued_contract(api, code)
    assert await _flag(api, code) == (True, True)
    # When
    then_status_is(await when_delete_contract(api, contract["id"]), 204)
    # Then
    assert await _flag(api, code) == (False, False)


async def test_the_flag_belongs_to_each_deal(api: Api) -> None:
    """Scenario: 한 Deal의 발급은 다른 Deal의 플래그에 영향이 없다."""
    # Given
    await given_logged_in_as(api)
    issued = await given_won_deal(api)
    other = await given_won_deal(api, name="다른 Deal")
    await given_issued_contract(api, issued)
    # When / Then
    assert await _flag(api, issued) == (True, True)
    assert await _flag(api, other) == (False, False)


async def test_deal_is_won_on_the_contract_follows_the_deal(api: Api) -> None:
    """Scenario: 계약 응답의 deal_is_won은 Deal이 Won일 때만 true고, 이탈하면 false가 된다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    # When / Then
    assert (await when_get_contract(api, contract["id"])).json()["deal_is_won"] is True
    then_status_is(await when_leave_won_by_change(api, code, delete=False), 200)
    assert (await when_get_contract(api, contract["id"])).json()["deal_is_won"] is False
