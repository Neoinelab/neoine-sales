"""Feature: Deal이 참조하는 연락처는 지울 수 없고, 참조가 없으면 지워진다.

고객으로든 파트너로든 Deal이 참조하면 409 '연결된 Deal이 N건 있어 삭제할 수 없습니다.'이다(AC-22).
한 Deal이 같은 연락처를 고객과 파트너로 둘 다 참조해 1건으로 세는 경우는 API로 만들 수 없어
(구분 검사가 막는다) 저장소 계약(test_contact_delete_contract.py)이 본다. 구 삭제 시나리오
(test_customers_api, test_partners_api의 DELETE)를 옮겼다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.contacts import (
    given_contact,
    in_use_message,
    then_contact_is_listed,
    then_contact_is_not_listed,
    then_detail_is,
    then_total_contacts_are,
    when_delete_contact,
)
from tests.functional.steps.deals import given_deal_deleted, given_deal_of_contacts

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("kind", ["customer", "partner"])
async def test_admin_deletes_a_contact_nobody_references(api: Api, kind: str) -> None:
    """Scenario: 참조하는 Deal이 없으면 204로 삭제되고 목록에서 사라진다."""
    # Given
    await given_logged_in_as(api, role="admin")
    keep = await given_contact(api, kind, company="유지회사")
    gone = await given_contact(api, kind, company="삭제회사", name="박영희", email=None)
    # When
    response = await when_delete_contact(api, gone["id"])
    # Then
    then_status_is(response, 204)
    assert response.content == b""
    await then_contact_is_not_listed(api, gone["id"])
    await then_contact_is_listed(api, keep["id"])


async def test_deleting_an_unknown_or_already_deleted_contact_is_404(api: Api) -> None:
    """Scenario: 이미 지운 연락처나 없는 id를 지우면 404이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    created = await given_contact(api)
    await when_delete_contact(api, created["id"])
    # When
    again = await when_delete_contact(api, created["id"])
    unknown = await when_delete_contact(api, str(uuid4()))
    # Then
    then_problem_is(again, status=404, type_suffix="not-found")
    then_problem_is(unknown, status=404, type_suffix="not-found")


async def test_deleting_with_a_malformed_id_is_a_request_validation_error(api: Api) -> None:
    """Scenario: id가 UUID 형식이 아니면 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_contact(api, "not-a-uuid")
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_a_contact_used_as_the_customer_of_a_deal_cannot_be_deleted(api: Api) -> None:
    """Scenario: 고객으로 Deal이 참조하는 연락처를 지우면 409(invalid-state)이고 그대로 남는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    customer = await given_contact(api, "customer")
    await given_deal_of_contacts(api, customer_id=customer["id"])
    # When
    response = await when_delete_contact(api, customer["id"])
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_detail_is(response, in_use_message(1))
    await then_contact_is_listed(api, customer["id"])


async def test_a_contact_used_as_the_partner_of_a_deal_cannot_be_deleted(api: Api) -> None:
    """Scenario: 파트너로 Deal이 참조하는 연락처를 지우면 409이고 그대로 남는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    customer = await given_contact(api, "customer")
    partner = await given_contact(api, "partner")
    await given_deal_of_contacts(api, customer_id=customer["id"], partner_id=partner["id"])
    # When
    response = await when_delete_contact(api, partner["id"])
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_detail_is(response, in_use_message(1))
    await then_contact_is_listed(api, partner["id"])


async def test_the_conflict_message_counts_every_referencing_deal(api: Api) -> None:
    """Scenario: Deal이 여러 건이면 그 건수가 문구에 들어간다."""
    # Given
    await given_logged_in_as(api, role="admin")
    customer = await given_contact(api, "customer")
    for _ in range(3):
        await given_deal_of_contacts(api, customer_id=customer["id"])
    # When
    response = await when_delete_contact(api, customer["id"])
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_detail_is(response, in_use_message(3))


async def test_a_contact_can_be_deleted_once_its_deals_are_gone(api: Api) -> None:
    """Scenario: 참조하던 Deal을 지우면 연락처도 지울 수 있다."""
    # Given
    await given_logged_in_as(api, role="admin")
    customer = await given_contact(api, "customer")
    deal = await given_deal_of_contacts(api, customer_id=customer["id"])
    await given_deal_deleted(api, deal["code"])
    # When
    response = await when_delete_contact(api, customer["id"])
    # Then
    then_status_is(response, 204)
    await then_total_contacts_are(api, 0)


async def test_deals_of_other_contacts_do_not_block_the_deletion(api: Api) -> None:
    """Scenario: 다른 연락처를 참조하는 Deal은 이 연락처의 삭제를 막지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    free = await given_contact(api, company="한가한회사", name="박영희", email=None)
    busy = await given_contact(api, company="바쁜회사")
    await given_deal_of_contacts(api, customer_id=busy["id"])
    # When
    response = await when_delete_contact(api, free["id"])
    # Then
    then_status_is(response, 204)
    await then_contact_is_listed(api, busy["id"])
