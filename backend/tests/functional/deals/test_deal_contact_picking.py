"""Feature: Deal 화면에서 연락처를 고르고 고친다.

연락처를 고르면(contact_id) 입력값으로 그 연락처를 갱신해 쓰고, 정보가 실제로 바뀌면 그 연락처를
참조하는 다른 모든 Deal(비활성 파트너 링크 포함)의 이력에 한 건씩 남는다. 같은 사람이면 재사용한다.
종류가 다르거나 없는 연락처는 404, 다른 사람과 겹치면 409다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    CONTACT_NOT_FOUND,
    DUPLICATE_CONTACT,
    customer_draft,
    given_deal,
    partner_draft,
    then_deal_count_is,
    then_deal_keeps,
    then_history_is,
    when_register_deal,
    when_update_deal,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

BEFORE = "직급 팀장 · 이메일 kim@neoine.example · 전화 010-1234-5678"
AFTER = "직급 이사 · 이메일 kim@neoine.example · 전화 010-1234-5678"
CONTACT_TARGET = "고객 연락처 정보 (네오인 김철수)"


def _pick(deal: dict[str, object], key: str = "customer", **changes: object) -> dict[str, object]:
    """이미 있는 연락처를 고르는 입력(값은 현재 그대로, changes만 바꾼다)."""
    contact = deal[key]
    assert isinstance(contact, dict)
    base = {name: contact[name] for name in ("company", "name", "title", "email", "phone")}
    return {"contact_id": contact["id"], **base, **changes}


async def test_picking_a_contact_with_new_values_updates_it_and_logs_every_other_deal(
    api: Api,
) -> None:
    """Scenario: 연락처 값을 고쳐 고르면 그 연락처를 쓰는 다른 Deal 이력에 한 건씩 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    first = await given_deal(api)
    second = await given_deal(api)
    # When
    response = await when_register_deal(api, customer=_pick(first, title="이사"))
    # Then
    then_status_is(response, 201)
    assert response.json()["customer"]["id"] == first["customer"]["id"]
    assert response.json()["customer"]["title"] == "이사"
    expected = [("contact", CONTACT_TARGET, BEFORE, AFTER)]
    await then_history_is(api, first["code"], expected)
    await then_history_is(api, second["code"], expected)
    await then_history_is(api, response.json()["code"], [])  # 새 Deal은 등록 이력뿐


async def test_the_other_deals_are_touched_when_a_contact_changes(api: Api) -> None:
    """Scenario: 연락처가 바뀌면 그 연락처를 쓰는 다른 Deal의 updated_at이 갱신된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    first = await given_deal(api)
    api.clock.advance(3600)
    # When
    await when_register_deal(api, customer=_pick(first, phone="02-123-4567"))
    # Then
    refreshed = await api.get(f"/api/v1/deals/{first['code']}")
    assert refreshed.json()["updated_at"] > first["updated_at"]


async def test_picking_a_contact_without_changes_leaves_no_trace(api: Api) -> None:
    """Scenario: 값을 그대로 고르면 연락처도 다른 Deal 이력도 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    first = await given_deal(api)
    api.clock.advance(3600)
    # When
    response = await when_register_deal(api, customer=_pick(first))
    # Then
    then_status_is(response, 201)
    await then_history_is(api, first["code"], [])
    await then_deal_keeps(api, first["code"], updated_at=first["updated_at"])


async def test_a_replaced_partner_link_still_gets_the_contact_log(api: Api) -> None:
    """Scenario: 파트너가 교체되어 비활성이 된 Deal의 이력에도 연락처 갱신이 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, partner=partner_draft())
    old_partner = deal["active_partner"]
    await when_update_deal(
        api, deal["code"], partner=partner_draft(company="에이원", name="표성호")
    )
    # When
    response = await when_register_deal(
        api,
        customer=customer_draft(company="신규고객", name="오세훈"),
        partner=_pick(deal, "active_partner", phone="02-999-8888"),
    )
    # Then
    then_status_is(response, 201)
    assert old_partner["id"] == response.json()["active_partner"]["id"]
    history = await api.get(f"/api/v1/deals/{deal['code']}/history")
    targets = [h["target"] for h in history.json() if h["category"] == "contact"]
    assert targets == ["파트너 연락처 정보 (한빛파트너스 이영희)"]


async def test_the_same_person_is_reused_and_blank_values_do_not_erase(api: Api) -> None:
    """Scenario: 같은 회사·이름이면 기존 연락처를 쓰고 빈 입력은 기존 값을 지우지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    first = await given_deal(api)
    # When
    second = await given_deal(api, customer=customer_draft(title=None, email=None, phone=None))
    # Then
    assert second["customer"]["id"] == first["customer"]["id"]
    assert second["customer"]["title"] == "팀장"
    assert second["customer"]["email"] == "kim@neoine.example"
    assert second["customer"]["phone"] == "010-1234-5678"


async def test_a_different_email_is_a_different_person(api: Api) -> None:
    """Scenario: 같은 회사·이름이라도 이메일이 다르면 다른 사람이라 새 연락처가 만들어진다."""
    # Given
    await given_logged_in_as(api, role="sales")
    first = await given_deal(api)
    # When
    second = await given_deal(api, customer=customer_draft(email="other@neoine.example"))
    # Then
    assert second["customer"]["id"] != first["customer"]["id"]


async def test_a_contact_of_the_other_kind_is_not_found(api: Api) -> None:
    """Scenario: 파트너 연락처를 고객으로 고르면 404이고 Deal은 만들어지지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, partner=partner_draft())
    # When
    response = await when_register_deal(api, customer=_pick(deal, "active_partner"))
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    assert response.json()["detail"] == CONTACT_NOT_FOUND
    await then_deal_count_is(api, 1)


async def test_an_unknown_contact_id_is_not_found(api: Api) -> None:
    """Scenario: 없는 연락처 id를 고르면 404이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, customer=customer_draft(contact_id=str(uuid4())))
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    assert response.json()["detail"] == CONTACT_NOT_FOUND
    await then_deal_count_is(api, 0)


async def test_turning_a_picked_contact_into_a_known_person_conflicts(api: Api) -> None:
    """Scenario: 고른 연락처를 이미 있는 다른 사람으로 바꾸려 하면 409(already-exists)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    kim = await given_deal(api)
    await given_deal(api, customer=customer_draft(name="박영희", email="park@neoine.example"))
    # When
    response = await when_register_deal(
        api, customer=_pick(kim, name="박영희", email="park@neoine.example")
    )
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    assert response.json()["detail"] == DUPLICATE_CONTACT
    await then_deal_keeps(api, kim["code"], customer=kim["customer"])


async def test_a_failed_registration_does_not_change_the_picked_contact(api: Api) -> None:
    """Scenario: 입력 오류로 등록이 실패하면 고른 연락처도 바뀌지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    first = await given_deal(api)
    # When
    response = await when_register_deal(api, customer=_pick(first, title="이사"), revenue_amount=0)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_history_is(api, first["code"], [])
    await then_deal_keeps(api, first["code"], customer=first["customer"])
