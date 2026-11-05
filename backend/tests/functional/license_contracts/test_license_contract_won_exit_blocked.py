"""Feature: 발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없다.

발급 상태(발급(신규)·발급(갱신)) 계약이 있으면 인라인 변경, Deal 폼, Action 등록 어느 경로로든
Won을 벗어나는 요청이 409(invalid-state)로 거절되고 아무것도 바뀌지 않는다.
`delete_license_contracts` 값(true·false·생략)과 무관하다.
잘못 작성한 계약은 admin이 삭제하면 다시 Won을 벗어날 수 있다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import when_list_actions
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.license_contracts import (
    WON_EXIT_BLOCKED,
    contracts_of,
    given_contract_file,
    given_issued_contract,
    given_won_deal,
    then_contract_disk_holds,
    then_contract_folder_exists,
    then_contract_row_count_is,
    then_file_row_count_is,
    then_statuses_are,
    when_delete_contract,
    when_end,
    when_leave_won_by_action,
    when_leave_won_by_change,
    when_leave_won_by_form,
)
from tests.functional.steps.users import given_signed_in_session

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Any

    from httpx import Response

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

LEAVERS: dict[str, Callable[..., Awaitable[Response]]] = {
    "change": when_leave_won_by_change,
    "form": when_leave_won_by_form,
    "action": when_leave_won_by_action,
}
SUCCESS = {"change": 200, "form": 200, "action": 201}


async def _won_deal_with_an_issued_contract(api: Api) -> tuple[str, dict[str, Any]]:
    """발급(신규) 계약과 그 계약의 첨부 하나를 가진 Won Deal."""
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_issued_contract(api, code)
    await given_contract_file(api, contract["id"], name="signed.pdf", data=b"signed-bytes")
    return code, contract


async def _then_nothing_changed(api: Api, code: str, contract: dict[str, Any]) -> None:
    deal = (await api.get(f"/api/v1/deals/{code}")).json()
    assert (deal["status_key"], deal["forecast_key"]) == ("contract_completed", "won")
    assert [(c["id"], c["status"]) for c in await contracts_of(api, code)] == [
        (contract["id"], "issued_new")
    ]
    await then_file_row_count_is(api, 1)
    then_contract_disk_holds(api, contract["id"], [b"signed-bytes"])


@pytest.mark.parametrize("flag", [None, True, False])
@pytest.mark.parametrize("path", list(LEAVERS))
async def test_leaving_won_with_an_issued_contract_is_rejected(
    api: Api, path: str, flag: bool | None
) -> None:
    """Scenario: 발급 계약이 있으면 세 경로 모두 409이고 Deal·계약·첨부 파일이 그대로다."""
    # Given
    code, contract = await _won_deal_with_an_issued_contract(api)
    # When
    response = await LEAVERS[path](api, code, delete=flag)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == WON_EXIT_BLOCKED
    await _then_nothing_changed(api, code, contract)


async def test_a_rejected_action_registration_saves_no_action(api: Api) -> None:
    """Scenario: Action 등록으로 Won을 벗어나려다 거절되면 Action도 저장되지 않는다."""
    # Given
    code, _ = await _won_deal_with_an_issued_contract(api)
    # When
    response = await when_leave_won_by_action(api, code, delete=True)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    listed = await when_list_actions(api, code)
    assert listed.json()["items"] == []


async def test_a_renewed_contract_also_blocks_leaving_won(api: Api) -> None:
    """Scenario: 발급(갱신) 계약만 있어도 Won을 벗어날 수 없다."""
    # Given
    code, contract = await _won_deal_with_an_issued_contract(api)
    from tests.functional.steps.license_contracts import when_renew  # noqa: PLC0415

    renewal = (await when_renew(api, contract["id"])).json()
    # When
    response = await when_leave_won_by_change(api, code, delete=True)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    await then_statuses_are(api, code, ["ended", "issued_renewal"])
    assert renewal["status"] == "issued_renewal"


async def test_an_ended_contract_no_longer_blocks_leaving_won(api: Api) -> None:
    """Scenario: 발급 계약을 종료하면 Won을 벗어날 수 있고 '유지'면 계약이 남는다."""
    # Given
    code, contract = await _won_deal_with_an_issued_contract(api)
    then_status_is(await when_end(api, contract["id"]), 200)
    # When
    response = await when_leave_won_by_change(api, code, delete=False)
    # Then
    then_status_is(response, 200)
    await then_statuses_are(api, code, ["ended"])


async def test_after_the_admin_deletes_the_issued_contract_the_deal_can_leave_won(
    api: Api,
) -> None:
    """Scenario: 잘못 작성된 발급 계약을 admin이 삭제하면 같은 Deal의 Won 이탈이 된다."""
    # Given
    code, contract = await _won_deal_with_an_issued_contract(api)
    blocked = await when_leave_won_by_change(api, code, delete=True)
    then_status_is(blocked, 409)
    then_status_is(await when_delete_contract(api, contract["id"]), 204)
    # When
    response = await when_leave_won_by_change(api, code, delete=True)
    # Then
    then_status_is(response, 200)
    deal = (await api.get(f"/api/v1/deals/{code}")).json()
    assert (deal["status_key"], deal["forecast_key"]) == ("poc_completed", "commit")
    await then_contract_row_count_is(api, code, 0)


async def test_sales_cannot_delete_the_issued_contract_to_get_around_the_rule(api: Api) -> None:
    """Scenario: sales는 계약을 지울 수 없으므로(403) 발급 계약이 있는 Deal은 여전히 Won이다."""
    # Given
    code, contract = await _won_deal_with_an_issued_contract(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    # When
    deleted = await when_delete_contract(api, contract["id"], session=kim)
    left = await when_leave_won_by_change(api, code, delete=True, session=kim)
    # Then
    then_problem_is(deleted, status=403, type_suffix="forbidden")
    then_problem_is(left, status=409, type_suffix="invalid-state")
    await _then_nothing_changed(api, code, contract)
    then_contract_folder_exists(api, contract["id"])
