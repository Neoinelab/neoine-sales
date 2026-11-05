"""Feature: Deal을 지우면 그 Deal의 라이선스 계약·계약 첨부도 함께 지워지고 건수를 알려 준다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.attachments import given_file, then_deal_directory_is_gone
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deals import DEALS
from tests.functional.steps.license_contracts import (
    contracts_of,
    given_contract_file,
    given_contract_of,
    given_issued_contract,
    given_open_deal,
    given_won_deal,
    then_contract_disk_holds,
    then_contract_folder_is_gone,
    then_contract_row_count_is,
    then_file_row_count_is,
    when_delete_deal_with_contracts,
    when_renew,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_the_deletion_impact_counts_the_license_contracts(api: Api) -> None:
    """Scenario: 삭제 영향 조회에 license_contract_count가 있다(갱신으로 늘어난 계약 포함)."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    first = await given_issued_contract(api, code)
    then_status_is(await when_renew(api, first["id"]), 201)
    # When
    response = await api.get(f"{DEALS}/{code}/deletion-impact")
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert body["license_contract_count"] == 2
    assert {"history_count", "action_count", "attachment_count"} <= set(body)


async def test_a_deal_without_contracts_reports_zero(api: Api) -> None:
    """Scenario: 계약이 없는 Deal의 건수는 0이다."""
    # Given
    await given_logged_in_as(api)
    code = await given_open_deal(api)
    # When
    response = await api.get(f"{DEALS}/{code}/deletion-impact")
    # Then
    assert response.json()["license_contract_count"] == 0


async def test_contract_attachments_do_not_count_as_deal_attachments(api: Api) -> None:
    """Scenario: 계약 첨부는 attachment_count(Deal 첨부)에 섞이지 않는다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    await given_contract_file(api, contract["id"])
    await given_file(api, code, name="deal.pdf")
    # When
    response = await api.get(f"{DEALS}/{code}/deletion-impact")
    # Then
    assert response.json()["attachment_count"] == 1


async def test_deleting_the_deal_removes_contracts_attachment_rows_and_files(api: Api) -> None:
    """Scenario: Deal 삭제로 계약·계약 첨부 행이 사라지고 Deal 폴더와 계약 폴더도 지워진다."""
    # Given
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    other = await given_won_deal(api, name="남는 Deal")
    contract = await given_issued_contract(api, code)
    await given_contract_file(api, contract["id"], name="c.pdf", data=b"contract")
    kept = await given_contract_of(api, other)
    await given_contract_file(api, kept["id"], name="kept.pdf", data=b"kept")
    await given_file(api, code, name="deal.pdf", data=b"deal-bytes")
    then_contract_disk_holds(api, contract["id"], [b"contract"])
    # When
    response = await when_delete_deal_with_contracts(api, code)
    # Then
    then_status_is(response, 204)
    assert await contracts_of(api, code) == []
    await then_contract_row_count_is(api, code, 0)
    await then_file_row_count_is(api, 1)  # 다른 Deal의 계약 첨부 행만 남는다
    then_deal_directory_is_gone(api, code)  # Deal 폴더
    then_contract_folder_is_gone(api, contract["id"])  # 그 Deal의 계약 폴더
    then_contract_disk_holds(api, kept["id"], [b"kept"])  # 다른 Deal의 계약 폴더는 남는다
    assert [c["id"] for c in await contracts_of(api, other)] == [kept["id"]]
