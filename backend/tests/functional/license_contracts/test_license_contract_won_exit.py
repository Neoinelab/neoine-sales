"""Feature: Won인 Deal을 Won이 아닌 상태로 바꿀 때 라이선스 계약을 함께 지울지 고른다.

Status 변경 요청의 선택 필드 `delete_license_contracts`(기본 false = 유지)다. true면 그 Deal의
계약과 계약 첨부 행이 모두 지워지고 계약 폴더(`license-contracts/<id>`)도 사라지며 Deal 자체의
첨부 파일은 남는다. 발급 계약이 있으면 거절된다(test_license_contract_won_exit_blocked.py).
Won을 벗어나는 변경이 아니면 플래그는 무시된다. 경로: 인라인 변경, Deal 폼, Action 등록.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.attachments import given_file, then_disk_holds
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.license_contracts import (
    contracts_of,
    given_contract_file,
    given_contract_of,
    given_open_deal,
    given_won_deal,
    then_contract_disk_holds,
    then_contract_folder_is_gone,
    then_contract_row_count_is,
    then_deal_reports_contract_count,
    then_file_row_count_is,
    then_statuses_are,
    when_leave_won_by_action,
    when_leave_won_by_change,
    when_leave_won_by_form,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from httpx import Response

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

LEAVERS: dict[str, Callable[..., Awaitable[Response]]] = {
    "change": when_leave_won_by_change,
    "form": when_leave_won_by_form,
    "action": when_leave_won_by_action,
}
SUCCESS = {"change": 200, "form": 200, "action": 201}


async def _won_deal_with_files(api: Api) -> tuple[str, dict[str, object]]:
    """Won Deal, 계약 첨부 하나, Deal 자체의 첨부 하나(같은 디렉터리)."""
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    await given_contract_file(api, contract["id"], name="contract.pdf", data=b"contract-bytes")
    await given_file(api, code, name="deal.pdf", data=b"deal-bytes")
    return code, contract


@pytest.mark.parametrize("path", list(LEAVERS))
async def test_leaving_won_with_delete_removes_contracts_and_their_files(
    api: Api, path: str
) -> None:
    """Scenario: 삭제를 고르면 계약·계약 첨부 행과 파일이 지워지고 Deal 첨부 파일은 남는다."""
    # Given
    code, contract = await _won_deal_with_files(api)
    # When
    response = await LEAVERS[path](api, code, delete=True)
    # Then
    then_status_is(response, SUCCESS[path])
    assert await contracts_of(api, code) == []
    await then_contract_row_count_is(api, code, 0)
    await then_file_row_count_is(api, 0)
    then_contract_folder_is_gone(api, contract["id"])
    then_disk_holds(api, code, [b"deal-bytes"])
    await then_deal_reports_contract_count(api, code, 0)


@pytest.mark.parametrize("flag", [None, False])
@pytest.mark.parametrize("path", list(LEAVERS))
async def test_leaving_won_without_the_flag_keeps_contracts_and_files(
    api: Api, path: str, flag: bool | None
) -> None:
    """Scenario: 플래그를 생략하거나 false면 계약과 파일이 그대로 남는다."""
    # Given
    code, contract = await _won_deal_with_files(api)
    # When
    response = await LEAVERS[path](api, code, delete=flag)
    # Then
    then_status_is(response, SUCCESS[path])
    assert [c["id"] for c in await contracts_of(api, code)] == [contract["id"]]
    await then_file_row_count_is(api, 1)
    then_contract_disk_holds(api, contract["id"], [b"contract-bytes"])
    then_disk_holds(api, code, [b"deal-bytes"])
    await then_deal_reports_contract_count(api, code, 1)


async def test_the_deal_change_itself_is_applied_when_contracts_are_deleted(api: Api) -> None:
    """Scenario: 계약을 지우며 Won을 벗어나면 Deal의 Status·Forecast도 바뀐다."""
    # Given
    code, _ = await _won_deal_with_files(api)
    # When
    response = await when_leave_won_by_change(api, code, delete=True)
    # Then
    then_status_is(response, 200)
    deal = (await api.get(f"/api/v1/deals/{code}")).json()
    assert (deal["status_key"], deal["forecast_key"]) == ("poc_completed", "commit")


async def test_the_flag_is_ignored_when_the_change_does_not_leave_won(api: Api) -> None:
    """Scenario: Won인 채로 금액만 바꾸는 요청의 true 플래그는 무시되어 계약이 남는다."""
    # Given
    code, contract = await _won_deal_with_files(api)
    body = {
        "change": {"field": "revenue_amount", "value": 1_000_000},
        "delete_license_contracts": True,
    }
    # When
    response = await api.post(f"/api/v1/deals/{code}/changes", json=body)
    # Then
    then_status_is(response, 200)
    assert [c["id"] for c in await contracts_of(api, code)] == [contract["id"]]
    then_contract_disk_holds(api, contract["id"], [b"contract-bytes"])
    then_disk_holds(api, code, [b"deal-bytes"])


async def test_the_flag_is_ignored_for_a_deal_that_is_not_won(api: Api) -> None:
    """Scenario: Won이 아닌 Deal의 변경에 true를 보내도 오류 없이 무시된다."""
    # Given
    await given_logged_in_as(api)
    code = await given_open_deal(api)
    body = {
        "change": {"field": "forecast_key", "value": "commit"},
        "delete_license_contracts": True,
    }
    # When
    response = await api.post(f"/api/v1/deals/{code}/changes", json=body)
    # Then
    then_status_is(response, 200)
    assert await contracts_of(api, code) == []


async def test_a_rejected_change_with_the_flag_keeps_everything(api: Api) -> None:
    """Scenario: 함께 바꿀 Status를 고르지 않아 거절되면 계약도 파일도 그대로다."""
    # Given
    code, contract = await _won_deal_with_files(api)
    body = {
        "change": {"field": "forecast_key", "value": "commit"},
        "delete_license_contracts": True,
    }
    # When
    response = await api.post(f"/api/v1/deals/{code}/changes", json=body)
    # Then
    then_status_is(response, 422)
    assert [c["id"] for c in await contracts_of(api, code)] == [contract["id"]]
    then_contract_disk_holds(api, contract["id"], [b"contract-bytes"])
    then_disk_holds(api, code, [b"deal-bytes"])
    deal = (await api.get(f"/api/v1/deals/{code}")).json()
    assert deal["forecast_key"] == "won"


async def test_the_flag_must_be_a_boolean(api: Api) -> None:
    """Scenario: 불리언이 아닌 플래그는 422(request-validation)다."""
    # Given
    code, _ = await _won_deal_with_files(api)
    body = {
        "change": {"field": "forecast_key", "value": "commit"},
        "delete_license_contracts": "yes",
    }
    # When
    response = await api.post(f"/api/v1/deals/{code}/changes", json=body)
    # Then
    then_status_is(response, 422)
    assert response.json()["type"].endswith("request-validation")
    await then_statuses_are(api, code, ["not_issued"])


async def test_deleting_the_contracts_of_one_deal_leaves_other_deals_alone(api: Api) -> None:
    """Scenario: 한 Deal의 Won 이탈 삭제는 다른 Deal의 계약에 영향이 없다."""
    # Given
    code, _ = await _won_deal_with_files(api)
    other = await given_won_deal(api, name="다른 Deal")
    # When
    response = await when_leave_won_by_change(api, code, delete=True)
    # Then
    then_status_is(response, 200)
    await then_statuses_are(api, other, ["not_issued"])
