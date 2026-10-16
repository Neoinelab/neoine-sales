"""Feature: admin이 연락처를 고치면 그 연락처를 쓰는 모든 Deal의 History에 남는다.

고객으로 참조하는 Deal과 파트너로 연결한(해제한 링크 포함) Deal에 category=contact 한 건씩, 변경자는
고친 admin이고 그 Deal의 updated_at이 갱신된다. 정보가 그대로면 이력도 갱신도 없다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.contacts import (
    given_contact,
    update_payload,
    when_update_contact,
)
from tests.functional.steps.deals import (
    given_deal_of_contacts,
    given_my_user_id,
    then_history_is,
    when_get_deal,
    when_list_history,
    when_update_deal,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

CUSTOMER_TARGET = "고객 연락처 정보 (네오인 김철수)"
PARTNER_TARGET = "파트너 연락처 정보 (한빛파트너스 이영희)"
CUSTOMER_BEFORE = "직급 팀장 · 이메일 kim@neoine.example · 전화 010-1234-5678"
CUSTOMER_AFTER = "직급 이사 · 이메일 kim@neoine.example · 전화 010-1234-5678"
PARTNER_BEFORE = "직급 이사 · 이메일 lee@hanbit.example · 전화 02-123-4567"
PARTNER_AFTER = "직급 부장 · 이메일 lee@hanbit.example · 전화 02-123-4567"


async def test_changing_a_customer_logs_on_every_deal_that_uses_it(api: Api) -> None:
    """Scenario: 고객 연락처를 고치면 그 고객을 쓰는 모든 Deal 이력에 한 건씩 남는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    customer = await given_contact(api, "customer")
    first = await given_deal_of_contacts(api, customer_id=customer["id"])
    second = await given_deal_of_contacts(api, customer_id=customer["id"])
    api.clock.advance(3600)
    # When
    response = await when_update_contact(api, customer["id"], update_payload(title="이사"))
    # Then
    then_status_is(response, 200)
    for deal in (first, second):
        await then_history_is(
            api, deal["code"], [("contact", CUSTOMER_TARGET, CUSTOMER_BEFORE, CUSTOMER_AFTER)]
        )
        refreshed = await when_get_deal(api, deal["code"])
        assert refreshed.json()["updated_at"] > deal["updated_at"]


async def test_the_history_author_is_the_admin_who_changed_the_contact(api: Api) -> None:
    """Scenario: 이력의 변경자는 연락처를 고친 admin이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    customer = await given_contact(api, "customer")
    deal = await given_deal_of_contacts(api, customer_id=customer["id"])
    admin_id = await given_my_user_id(api)
    # When
    await when_update_contact(api, customer["id"], update_payload(title="이사"))
    # Then
    history = await when_list_history(api, deal["code"])
    assert history.json()[0]["category"] == "contact"
    assert history.json()[0]["by"]["id"] == admin_id


async def test_changing_a_partner_logs_with_the_partner_target(api: Api) -> None:
    """Scenario: 파트너 연락처를 고치면 '파트너 연락처 정보' 이력이 남는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    customer = await given_contact(api, "customer")
    partner = await given_contact(api, "partner")
    deal = await given_deal_of_contacts(api, customer_id=customer["id"], partner_id=partner["id"])
    # When
    response = await when_update_contact(
        api, partner["id"], update_payload("partner", title="부장")
    )
    # Then
    then_status_is(response, 200)
    await then_history_is(
        api, deal["code"], [("contact", PARTNER_TARGET, PARTNER_BEFORE, PARTNER_AFTER)]
    )


async def test_a_partner_link_that_was_replaced_still_gets_the_log(api: Api) -> None:
    """Scenario: 파트너를 교체한 뒤에도 이전 파트너 연락처를 고치면 그 Deal에 이력이 남는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    customer = await given_contact(api, "customer")
    old = await given_contact(api, "partner")
    other = await given_contact(api, "partner", company="에이원시스템", name="표성호", email=None)
    deal = await given_deal_of_contacts(api, customer_id=customer["id"], partner_id=old["id"])
    replace = {
        "contact_id": other["id"],
        "company": "에이원시스템",
        "name": "표성호",
        "title": other["title"],
        "email": None,
        "phone": other["phone"],
    }
    await when_update_deal(api, deal["code"], partner=replace)
    # When
    await when_update_contact(api, old["id"], update_payload("partner", title="부장"))
    # Then
    history = await when_list_history(api, deal["code"])
    targets = [entry["target"] for entry in history.json()]
    assert PARTNER_TARGET in targets


async def test_an_unchanged_contact_leaves_no_history_and_does_not_touch_the_deal(
    api: Api,
) -> None:
    """Scenario: 값이 그대로인 수정은 Deal 이력도 수정 시각도 바꾸지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    customer = await given_contact(api, "customer")
    deal = await given_deal_of_contacts(api, customer_id=customer["id"])
    api.clock.advance(3600)
    # When
    response = await when_update_contact(api, customer["id"], update_payload())
    # Then
    then_status_is(response, 200)
    await then_history_is(api, deal["code"], [])
    refreshed = await when_get_deal(api, deal["code"])
    assert refreshed.json()["updated_at"] == deal["updated_at"]


async def test_a_contact_without_deals_changes_without_any_history(api: Api) -> None:
    """Scenario: 쓰는 Deal이 없는 연락처를 고쳐도 오류 없이 수정된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    idle = await given_contact(api, "partner")
    # When
    response = await when_update_contact(api, idle["id"], update_payload("partner", title="상무"))
    # Then
    then_status_is(response, 200)
    assert response.json()["title"] == "상무"
