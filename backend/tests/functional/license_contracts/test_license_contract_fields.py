"""Feature: 계약 칸(기술담당·점검주기·Note)을 수정한다. Deal에서 읽는 칸은 계약에서 바꿀 수 없다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import when_update_deal
from tests.functional.steps.license_contracts import (
    given_contract_of,
    given_issued_contract,
    given_won_deal,
    then_contract_has_the_documented_keys,
    when_get_contract,
    when_update_contract,
    when_update_contract_body,
)
from tests.functional.steps.vendors import given_vendor
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_updating_the_contract_fields_is_saved(api: Api) -> None:
    """Scenario: 기술담당·점검주기·Note 수정이 저장되고 다시 조회해도 같다."""
    # Given
    await given_logged_in_as(api)
    contract = await given_contract_of(api, await given_won_deal(api))
    # When
    response = await when_update_contract(
        api, contract["id"], tech_owner="이기술", inspection_cycle="quarterly", note="분기 점검"
    )
    # Then
    then_status_is(response, 200)
    then_contract_has_the_documented_keys(response.json())
    saved = (await when_get_contract(api, contract["id"])).json()
    assert (saved["tech_owner"], saved["inspection_cycle"], saved["note"]) == (
        "이기술",
        "quarterly",
        "분기 점검",
    )
    assert saved["status"] == "not_issued"
    assert saved["updated_at"] >= contract["updated_at"]


async def test_updating_an_issued_contract_keeps_its_period(api: Api) -> None:
    """Scenario: 발급된 계약의 칸 수정은 상태와 기간을 건드리지 않는다."""
    # Given
    await given_logged_in_as(api)
    issued = await given_issued_contract(api, await given_won_deal(api))
    # When
    response = await when_update_contract(api, issued["id"], tech_owner="새 담당")
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert body["status"] == "issued_new"
    assert (body["license_start"], body["license_end"]) == ("2026-01-01", "2026-12-31")
    assert body["term"] == {"amount": 1, "unit": "year"}


async def test_the_fields_default_to_empty_when_omitted(api: Api) -> None:
    """Scenario: 보내지 않은 칸은 기본값(빈 값, 점검주기 없음)으로 저장된다."""
    # Given
    await given_logged_in_as(api)
    contract = await given_contract_of(api, await given_won_deal(api))
    then_status_is(
        await when_update_contract(
            api, contract["id"], tech_owner="x", inspection_cycle="yearly", note="y"
        ),
        200,
    )
    # When
    response = await when_update_contract(api, contract["id"])
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert (body["tech_owner"], body["inspection_cycle"], body["note"]) == ("", "none", "")


@pytest.mark.parametrize(
    "extra",
    [
        {"customer": "다른 고객"},
        {"vendor": {"id": 1}},
        {"product": "다른 제품"},
        {"partner": "다른 파트너"},
        {"sales_owner": 1},
        {"status": "ended"},
        {"license_end": "2030-01-01"},
    ],
)
async def test_deal_owned_columns_and_unknown_fields_are_rejected(
    api: Api, extra: dict[str, object]
) -> None:
    """Scenario: Deal에서 읽는 칸·상태·기간을 계약 수정 요청에 보내면 422(request-validation)다."""
    # Given
    await given_logged_in_as(api)
    contract = await given_contract_of(api, await given_won_deal(api))
    # When
    response = await when_update_contract_body(api, contract["id"], {"tech_owner": "x", **extra})
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    assert (await when_get_contract(api, contract["id"])).json()["tech_owner"] == ""


@pytest.mark.parametrize(
    "body",
    [
        {"tech_owner": "가" * 101},
        {"note": "가" * 2001},
        {"inspection_cycle": "weekly"},
    ],
)
async def test_values_over_the_limits_are_rejected_and_nothing_is_saved(
    api: Api, body: dict[str, object]
) -> None:
    """Scenario: 길이 제한(100자·2000자)이나 허용 값을 어기면 422이고 저장되지 않는다."""
    # Given
    await given_logged_in_as(api)
    contract = await given_contract_of(api, await given_won_deal(api))
    # When
    response = await when_update_contract_body(api, contract["id"], body)
    # Then
    assert response.status_code == 422, response.text
    saved = (await when_get_contract(api, contract["id"])).json()
    assert (saved["tech_owner"], saved["note"]) == ("", "")


@pytest.mark.parametrize(
    ("body", "length_field"),
    [({"tech_owner": "가" * 100}, "tech_owner"), ({"note": "가" * 2000}, "note")],
)
async def test_values_at_the_limits_are_accepted(
    api: Api, body: dict[str, object], length_field: str
) -> None:
    """Scenario: 기술담당 100자, Note 2000자는 저장된다."""
    # Given
    await given_logged_in_as(api)
    contract = await given_contract_of(api, await given_won_deal(api))
    # When
    response = await when_update_contract_body(api, contract["id"], body)
    # Then
    then_status_is(response, 200)
    assert len(response.json()[length_field]) == len(str(body[length_field]))


async def test_updating_a_missing_contract_is_404(api: Api) -> None:
    """Scenario: 없는 계약의 수정은 404다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_update_contract(api, MISSING_ID, tech_owner="x")
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


async def test_deal_values_in_the_contract_follow_the_deal(api: Api) -> None:
    """Scenario: 고객사명·제품명·Vendor·담당영업은 Deal 값이라 Deal을 고치면 계약 응답도 바뀐다."""
    # Given
    await given_logged_in_as(api)
    sap = await given_vendor(api, "SAP")
    code = await given_won_deal(api)
    contract = await given_contract_of(api, code)
    assert contract["vendor"] is None
    assert contract["product"] == "S/4HANA"
    # When
    response = await when_update_deal(api, code, vendor_id=sap.id, solution="ITDR")
    # Then
    then_status_is(response, 200)
    reread = (await when_get_contract(api, contract["id"])).json()
    assert reread["vendor"] == {"id": sap.id, "name": "SAP"}
    assert reread["product"] == "ITDR"
    assert reread["customer"] == contract["customer"]
    assert reread["sales_owner"]["id"] == contract["sales_owner"]["id"]
