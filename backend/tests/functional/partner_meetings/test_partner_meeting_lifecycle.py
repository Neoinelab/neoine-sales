"""Feature: 미팅 기록은 Deal·사용자·연락처의 변화에도 이력으로 남는다(또는 Deal과 함께 지워진다).

Deal을 지우면 그 Deal의 미팅 기록도 함께 지워지고 삭제 영향 건수에 미팅 건수가 보인다. 미팅을 쓴
사용자를 삭제하면 퇴사 처리되어 작성자 열에 '(퇴사)'로 남고 작성자 선택지에도 나온다.
연락처 회사명을
바꿔도 기존 기록은 저장된 회사명 그대로다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.contacts import (
    update_payload,
    when_search_contacts,
    when_update_contact,
)
from tests.functional.steps.deals import when_delete_deal
from tests.functional.steps.partner_meetings import (
    HANBIT,
    contents_of,
    given_many_meetings,
    given_meeting,
    given_meeting_by,
    given_partner_deal,
    meeting_item,
    then_all_contents_are,
    when_get_deal_options,
    when_get_deletion_impact,
    when_list_meetings,
    when_register_meetings,
)
from tests.functional.steps.users import (
    given_signed_in_session,
    id_of,
    when_delete_user,
    when_list_options,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_the_deletion_impact_counts_the_meetings_of_that_deal(api: Api) -> None:
    """Scenario: Deal 삭제 영향에 그 Deal의 미팅 건수가 나온다(다른 Deal 것은 세지 않는다)."""
    # Given
    await given_logged_in_as(api)
    first = await given_partner_deal(api, name="ERP", contact="가나다")
    second = await given_partner_deal(api, name="MES", contact="라마바")
    await given_many_meetings(api, first["code"], 3)
    await given_meeting(api, second["code"])
    # When
    response = await when_get_deletion_impact(api, first["code"])
    # Then
    then_status_is(response, 200)
    assert response.json()["partner_meeting_count"] == 3
    other = await when_get_deletion_impact(api, second["code"])
    assert other.json()["partner_meeting_count"] == 1


async def test_a_deal_without_meetings_has_a_zero_count(api: Api) -> None:
    """Scenario: 미팅이 없는 Deal의 삭제 영향 건수는 0이다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api)
    # When
    response = await when_get_deletion_impact(api, deal["code"])
    # Then
    assert response.json()["partner_meeting_count"] == 0


async def test_deleting_a_deal_deletes_its_meetings_and_keeps_the_others(api: Api) -> None:
    """Scenario: Deal을 지우면 그 Deal의 미팅은 함께 지워지고 다른 Deal의 미팅은 남는다."""
    # Given
    await given_logged_in_as(api)
    doomed = await given_partner_deal(api, name="지울 Deal", contact="가나다")
    kept = await given_partner_deal(api, name="남길 Deal", contact="라마바")
    await given_meeting(api, doomed["code"], content="삭제될 기록")
    await given_meeting(api, kept["code"], content="남을 기록", meeting_date="2027-03-02")
    # When
    response = await when_delete_deal(api, doomed["code"])
    # Then
    then_status_is(response, 204)
    await then_all_contents_are(api, ["남을 기록"])


async def test_a_user_who_wrote_a_meeting_is_resigned_and_stays_visible_as_the_author(
    api: Api,
) -> None:
    """Scenario: 미팅을 쓴 사용자를 삭제하면 퇴사 처리되고 작성자 열에 '(퇴사)'로 남는다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    await given_meeting_by(api, kim, deal["code"], content="퇴사자 기록")
    kim_id = await id_of(api, "kim")
    # When
    response = await when_delete_user(api, kim_id)
    # Then
    then_status_is(response, 200)
    listed = await when_list_meetings(api)
    assert contents_of(listed) == ["퇴사자 기록"]
    author = listed.json()["items"][0]["author"]
    assert author["resigned"] is True
    assert author["label"].endswith("(퇴사)")
    by_author = await when_list_meetings(api, author_user_id=kim_id)
    assert contents_of(by_author) == ["퇴사자 기록"]


async def test_a_resigned_author_is_in_the_author_choices(api: Api) -> None:
    """Scenario: 작성자 검색 선택지(include_resigned)에 퇴사한 작성자가 나온다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    await given_meeting_by(api, kim, deal["code"])
    kim_id = await id_of(api, "kim")
    await when_delete_user(api, kim_id)
    # When
    response = await when_list_options(api, include_resigned="true")
    # Then
    then_status_is(response, 200)
    assert kim_id in [item["id"] for item in response.json()["items"]]


async def test_renaming_the_contact_company_leaves_existing_records_unchanged(api: Api) -> None:
    """Scenario: 연락처 회사명을 바꿔도 기존 기록은 옛 이름이고 새 기록은 새 이름으로 입력한다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api, company=HANBIT, contact="가나다")
    await given_meeting(api, deal["code"], content="옛 이름 기록")
    contacts = await when_search_contacts(api, kind="partner")
    contact_id = contacts.json()["items"][0]["id"]
    renamed = await when_update_contact(
        api, contact_id, update_payload("partner", company="새회사명", name="가나다")
    )
    then_status_is(renamed, 200)
    # When
    listed = await when_list_meetings(api, partner=HANBIT)
    # Then
    assert [i["partner_company"] for i in listed.json()["items"]] == [HANBIT]
    assert (await when_get_deal_options(api, HANBIT)).json() == {"items": []}
    assert [o["code"] for o in (await when_get_deal_options(api, "새회사명")).json()["items"]] == [
        deal["code"]
    ]
    old_name_registration = await when_register_meetings(
        api, [meeting_item(deal["code"], company=HANBIT)]
    )
    assert old_name_registration.status_code == 422
    new_name_registration = await when_register_meetings(
        api, [meeting_item(deal["code"], company="새회사명")]
    )
    then_status_is(new_name_registration, 201)
