"""Feature: 영업은 Deal 수정 화면에서 자기 Deal의 연락처를 고르고 고친다.

PATCH로 고객이나 활성 파트너를 contact_id로 골라 값을 바꾸면 자기 Deal을 포함해 그 연락처를 쓰는
모든 Deal의 History에 contact 이력이 한 건씩 남고 수정 시각이 갱신된다. 종류가 다르거나 없는
연락처는 404, 다른 사람과 겹치면 409이며 그때는 아무것도 바뀌지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    CONTACT_NOT_FOUND,
    DUPLICATE_CONTACT,
    customer_draft,
    given_deal,
    partner_draft,
    then_history_is,
    when_update_deal,
)
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

CUSTOMER_TARGET = "고객 연락처 정보 (네오인 김철수)"
CUSTOMER_BEFORE = "직급 팀장 · 이메일 kim@neoine.example · 전화 010-1234-5678"
CUSTOMER_AFTER = "직급 이사 · 이메일 kim@neoine.example · 전화 010-1234-5678"
PARTNER_TARGET = "파트너 연락처 정보 (한빛파트너스 이영희)"
PARTNER_BEFORE = "직급 이사 · 이메일 lee@hanbit.example · 전화 02-123-4567"
PARTNER_AFTER = "직급 부장 · 이메일 lee@hanbit.example · 전화 02-123-4567"


def _pick(deal: dict[str, object], key: str = "customer", **changes: object) -> dict[str, object]:
    """이미 있는 연락처를 고르는 입력(값은 현재 그대로, changes만 바꾼다)."""
    contact = deal[key]
    assert isinstance(contact, dict)
    base = {name: contact[name] for name in ("company", "name", "title", "email", "phone")}
    return {"contact_id": contact["id"], **base, **changes}


async def test_editing_the_picked_customer_logs_on_the_own_deal_and_touches_it(api: Api) -> None:
    """Scenario: 자기 Deal의 고객을 고쳐 고르면 자기 Deal에 이력이 남고 수정 시각이 갱신된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    api.clock.advance(3600)
    # When
    response = await when_update_deal(api, deal["code"], customer=_pick(deal, title="이사"))
    # Then
    then_status_is(response, 200)
    assert response.json()["customer"]["title"] == "이사"
    assert response.json()["updated_at"] > deal["updated_at"]
    await then_history_is(
        api, deal["code"], [("contact", CUSTOMER_TARGET, CUSTOMER_BEFORE, CUSTOMER_AFTER)]
    )


async def test_editing_the_picked_customer_also_logs_on_the_other_deals_using_it(api: Api) -> None:
    """Scenario: 같은 고객을 쓰는 다른 Deal에도 이력이 한 건씩 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    first = await given_deal(api)
    second = await given_deal(api, customer=_pick(first))
    # When
    await when_update_deal(api, first["code"], customer=_pick(first, title="이사"))
    # Then
    expected = [("contact", CUSTOMER_TARGET, CUSTOMER_BEFORE, CUSTOMER_AFTER)]
    await then_history_is(api, first["code"], expected)
    await then_history_is(api, second["code"], expected)


async def test_editing_the_active_partner_logs_the_contact_info_without_a_partner_change(
    api: Api,
) -> None:
    """Scenario: 활성 파트너의 값을 고치면 '파트너 연락처 정보' 이력만 남고 링크는 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, partner=partner_draft())
    # When
    response = await when_update_deal(
        api, deal["code"], partner=_pick(deal, "active_partner", title="부장")
    )
    # Then
    then_status_is(response, 200)
    assert len(response.json()["partner_links"]) == 1
    await then_history_is(
        api, deal["code"], [("contact", PARTNER_TARGET, PARTNER_BEFORE, PARTNER_AFTER)]
    )


async def test_picking_the_same_values_leaves_no_history(api: Api) -> None:
    """Scenario: 값을 그대로 고르면 이력도 수정 시각 변화도 없다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    api.clock.advance(3600)
    # When
    response = await when_update_deal(api, deal["code"], customer=_pick(deal))
    # Then
    then_status_is(response, 200)
    assert response.json()["updated_at"] == deal["updated_at"]
    await then_history_is(api, deal["code"], [])


async def test_picking_a_contact_of_the_other_kind_is_not_found_and_changes_nothing(
    api: Api,
) -> None:
    """Scenario: 파트너 연락처를 고객으로 고르면 404이고 Deal은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, partner=partner_draft())
    partner_as_customer = _pick(deal, "active_partner")
    # When
    response = await when_update_deal(api, deal["code"], customer=partner_as_customer)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    assert response.json()["detail"] == CONTACT_NOT_FOUND
    await then_history_is(api, deal["code"], [])


async def test_picking_an_unknown_contact_is_not_found(api: Api) -> None:
    """Scenario: 없는 contact_id를 고르면 404이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_update_deal(
        api, deal["code"], customer=customer_draft(contact_id=MISSING_ID)
    )
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    assert response.json()["detail"] == CONTACT_NOT_FOUND


async def test_turning_the_picked_contact_into_another_known_person_conflicts(api: Api) -> None:
    """Scenario: 고른 연락처를 이미 있는 다른 사람과 같게 고치면 409이고 아무것도 바뀌지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_deal(api, customer=customer_draft(name="박영희", email=None))
    # When
    response = await when_update_deal(
        api, deal["code"], customer=_pick(deal, name="박영희", email=None)
    )
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    assert response.json()["detail"] == DUPLICATE_CONTACT
    await then_history_is(api, deal["code"], [])
