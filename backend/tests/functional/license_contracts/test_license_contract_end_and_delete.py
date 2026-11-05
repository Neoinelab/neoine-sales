"""Feature: 계약은 '계약 종료' 버튼으로만 종료되고(자동 종료 없음), 삭제는 admin만 할 수 있다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.attachments import disk_files
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.license_contracts import (
    ALREADY_ENDED,
    DELETE_ADMIN_ONLY,
    ISSUED_ONLY,
    NOT_ISSUED_ONLY,
    contracts_of,
    given_contract_file,
    given_contract_of,
    given_issued_contract,
    given_won_deal,
    then_contract_disk_holds,
    then_contract_folder_is_gone,
    then_contract_row_count_is,
    then_deal_reports_contract_count,
    then_file_row_count_is,
    when_delete_contract,
    when_end,
    when_get_contract,
    when_issue,
    when_renew,
    when_update_contract,
)
from tests.functional.steps.users import given_signed_in_session
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("first", ["not_issued", "issued_new"])
async def test_ending_a_contract_sets_ended_and_the_end_time(api: Api, first: str) -> None:
    """Scenario: 미발급·발급 계약의 '계약 종료'는 종료 상태와 종료 시각을 남긴다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    if first == "issued_new":
        contract = await given_issued_contract(api, code)
    # When
    response = await when_end(api, contract["id"])
    # Then
    then_status_is(response, 200)
    ended = response.json()
    assert ended["status"] == "ended"
    assert ended["ended_at"] is not None
    assert ended["license_start"] == contract["license_start"]
    assert ended["license_end"] == contract["license_end"]


async def test_nothing_ends_a_contract_automatically(api: Api) -> None:
    """Scenario: 종료일이 지나도 상태는 그대로다(자동 종료 없음)."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    issued = await given_issued_contract(api, code, start="2020-01-01", amount=1, unit="month")
    api.clock.advance(60 * 60 * 24 * 365)
    # When
    response = await when_get_contract(api, issued["id"])
    # Then
    then_status_is(response, 200)
    assert response.json()["status"] == "issued_new"


async def test_ending_twice_is_rejected(api: Api) -> None:
    """Scenario: 이미 종료된 계약을 다시 종료하면 409다."""
    # Given
    await given_logged_in_as(api)
    contract = await given_contract_of(api, await given_won_deal(api))
    first = (await when_end(api, contract["id"])).json()
    # When
    response = await when_end(api, contract["id"])
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == ALREADY_ENDED
    assert (await when_get_contract(api, contract["id"])).json()["ended_at"] == first["ended_at"]


async def test_an_ended_contract_cannot_be_issued_or_renewed_again(api: Api) -> None:
    """Scenario: 종료 후 재발급·재갱신은 409다."""
    # Given
    await given_logged_in_as(api)
    contract = await given_contract_of(api, await given_won_deal(api))
    then_status_is(await when_end(api, contract["id"]), 200)
    # When
    issue = await when_issue(api, contract["id"])
    renew = await when_renew(api, contract["id"])
    # Then
    assert issue.status_code == 409
    assert issue.json()["detail"] == NOT_ISSUED_ONLY
    assert renew.status_code == 409
    assert renew.json()["detail"] == ISSUED_ONLY


async def test_an_ended_contract_still_accepts_field_edits_and_attachments(api: Api) -> None:
    """Scenario: 종료된 계약도 계약 칸 수정과 첨부 업로드는 할 수 있다."""
    # Given
    await given_logged_in_as(api)
    contract = await given_contract_of(api, await given_won_deal(api))
    then_status_is(await when_end(api, contract["id"]), 200)
    # When
    updated = await when_update_contract(api, contract["id"], note="종료 후 메모")
    attached = await given_contract_file(api, contract["id"])
    # Then
    then_status_is(updated, 200)
    assert updated.json()["note"] == "종료 후 메모"
    assert updated.json()["status"] == "ended"
    assert attached["file_name"] == "a.pdf"


async def test_end_of_a_missing_contract_is_404(api: Api) -> None:
    """Scenario: 없는 계약을 종료하면 404다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_end(api, MISSING_ID)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


@pytest.mark.parametrize("first", ["not_issued", "issued_new", "ended"])
async def test_admin_deletes_a_contract_in_any_status(api: Api, first: str) -> None:
    """Scenario: admin은 상태와 무관하게 계약을 삭제할 수 있다(204)."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    if first == "issued_new":
        contract = await given_issued_contract(api, code)
    if first == "ended":
        then_status_is(await when_end(api, contract["id"]), 200)
    # When
    response = await when_delete_contract(api, contract["id"])
    # Then
    then_status_is(response, 204)
    assert await contracts_of(api, code) == []
    then_status_is(await when_get_contract(api, contract["id"]), 404)
    await then_deal_reports_contract_count(api, code, 0)


async def test_deleting_a_contract_removes_its_folder_but_not_other_contracts_folders(
    api: Api,
) -> None:
    """Scenario: 계약 삭제는 그 계약의 첨부 행과 계약 폴더만 지운다(다른 계약의 폴더는 남는다)."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    first = await given_issued_contract(api, code)
    renewal = (await when_renew(api, first["id"], start="2027-01-01")).json()
    await given_contract_file(api, first["id"], name="old.pdf", data=b"old-bytes")
    await given_contract_file(api, renewal["id"], name="new.pdf", data=b"new-bytes")
    # When
    response = await when_delete_contract(api, first["id"])
    # Then
    then_status_is(response, 204)
    await then_file_row_count_is(api, 1)
    then_contract_folder_is_gone(api, first["id"])  # 삭제한 계약의 폴더가 통째로 지워진다
    then_contract_disk_holds(api, renewal["id"], [b"new-bytes"])  # 다른 계약 폴더는 남는다
    assert disk_files(api, code) == []
    assert [c["id"] for c in await contracts_of(api, code)] == [renewal["id"]]
    assert (await when_get_contract(api, renewal["id"])).json()["renewed_from_id"] is None


async def test_sales_cannot_delete_a_contract(api: Api) -> None:
    """Scenario: sales의 계약 삭제는 403이고 계약은 그대로 남는다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    # When
    response = await when_delete_contract(api, contract["id"], session=kim)
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == DELETE_ADMIN_ONLY
    await then_contract_row_count_is(api, code, 1)


async def test_a_read_only_user_cannot_delete_a_contract(api: Api) -> None:
    """Scenario: user의 계약 삭제는 403이다."""
    # Given
    await given_logged_in_as(api)
    contract = await given_contract_of(api, await given_won_deal(api))
    viewer = await given_signed_in_session(api, login_id="viewer", role="user")
    # When
    response = await when_delete_contract(api, contract["id"], session=viewer)
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")


async def test_delete_of_a_missing_contract_is_404_even_for_sales(api: Api) -> None:
    """Scenario: 없는 계약의 삭제는 권한보다 먼저 404다."""
    # Given
    await given_logged_in_as(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    # When
    response = await when_delete_contract(api, MISSING_ID, session=kim)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
