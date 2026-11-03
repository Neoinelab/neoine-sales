"""Feature: 작성자 본인(sales)과 admin은 미팅 기록을 고치고 지운다.

판정 순서는 없는 기록 404 -> 권한 403 -> 값 422다. 회사를 바꾸지 않고 날짜·내용만 고치면
그 사이 연락처 회사명이 바뀌었어도 저장되고, 다른 회사로 바꿀 때만 회사 목록을 다시 검사한다.
미팅은 Deal과 무관하다. 삭제는 물리 삭제다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.contacts import update_payload, when_update_contact
from tests.functional.steps.partner_meetings import (
    COMPANY_NOT_FOUND,
    CONTENT_REQUIRED,
    DELETE_FORBIDDEN,
    EDIT_FORBIDDEN,
    HANBIT,
    NOT_FOUND,
    READ_ONLY,
    given_meeting_by,
    given_partner,
    meeting_item,
    then_all_contents_are,
    then_errors_are,
    when_delete_meeting,
    when_delete_meeting_as,
    when_list_meetings,
    when_update_meeting,
    when_update_meeting_as,
)
from tests.functional.steps.users import given_signed_in_session
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_the_author_edits_date_and_content(api: Api) -> None:
    """Scenario: 작성자가 날짜와 내용을 고치면 같은 id로 바뀌고 작성자·등록 시각은 그대로다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    created = await given_meeting_by(api, kim, content="이전 내용")
    body = meeting_item(content="수정한 내용", meeting_date="2027-04-15")
    # When
    response = await when_update_meeting_as(api, kim, created["id"], body)
    # Then
    then_status_is(response, 200)
    changed = response.json()
    assert changed["id"] == created["id"]
    assert (changed["content"], changed["meeting_date"]) == ("수정한 내용", "2027-04-15")
    assert changed["author"] == created["author"]
    assert changed["created_at"] == created["created_at"]
    assert changed["updated_at"] != created["updated_at"]
    await then_all_contents_are(api, ["수정한 내용"])


async def test_admin_edits_another_users_record(api: Api) -> None:
    """Scenario: admin은 남의 기록도 고치며 작성자는 바뀌지 않는다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    created = await given_meeting_by(
        api,
        kim,
    )
    # When
    response = await when_update_meeting(api, created["id"], meeting_item(content="관리자가 수정"))
    # Then
    then_status_is(response, 200)
    assert response.json()["content"] == "관리자가 수정"
    assert response.json()["author"] == created["author"]


async def test_an_unchanged_edit_keeps_the_updated_time(api: Api) -> None:
    """Scenario: 값이 하나도 바뀌지 않은 수정은 200이지만 수정 시각이 그대로다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    created = await given_meeting_by(
        api,
        kim,
    )
    # When
    response = await when_update_meeting_as(
        api,
        kim,
        created["id"],
        meeting_item(content=created["content"], meeting_date=created["meeting_date"]),
    )
    # Then
    then_status_is(response, 200)
    assert response.json()["updated_at"] == created["updated_at"]


async def test_another_sales_cannot_edit_and_the_record_is_unchanged(api: Api) -> None:
    """Scenario: 다른 sales의 수정은 403 안내 문구이고 기록은 그대로다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    created = await given_meeting_by(api, kim, content="원래 내용")
    # When
    response = await when_update_meeting_as(
        api, park, created["id"], meeting_item(content="가로채기")
    )
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == EDIT_FORBIDDEN
    await then_all_contents_are(api, ["원래 내용"])


async def test_a_read_only_user_cannot_edit(api: Api) -> None:
    """Scenario: 읽기 전용 사용자의 수정은 403 읽기 전용 문구다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    viewer = await given_signed_in_session(api, login_id="viewer", role="user")
    created = await given_meeting_by(
        api,
        kim,
    )
    # When
    response = await when_update_meeting_as(api, viewer, created["id"], meeting_item())
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == READ_ONLY


async def test_editing_a_missing_record_is_404_before_any_other_check(api: Api) -> None:
    """Scenario: 없는 기록은 값이 틀려도 404다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    park = await given_signed_in_session(api, login_id="park", role="sales")
    # When
    response = await when_update_meeting_as(
        api, park, MISSING_ID, meeting_item(company="없는회사", content="  ")
    )
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    assert response.json()["detail"] == NOT_FOUND


async def test_forbidden_comes_before_validation(api: Api) -> None:
    """Scenario: 남의 기록을 틀린 값으로 고치려 하면 422가 아니라 403이다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    created = await given_meeting_by(
        api,
        kim,
    )
    # When
    response = await when_update_meeting_as(api, park, created["id"], meeting_item(content="  "))
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")


async def test_a_blank_content_is_rejected_at_the_content_location(api: Api) -> None:
    """Scenario: 내용을 비우면 content 위치의 invalid-value 오류이고 기록은 그대로다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    created = await given_meeting_by(api, kim, content="남아야 함")
    # When
    response = await when_update_meeting_as(api, kim, created["id"], meeting_item(content="   "))
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_errors_are(response, [(("content",), CONTENT_REQUIRED)])
    await then_all_contents_are(api, ["남아야 함"])


async def test_author_changes_only_the_date_after_the_partner_company_was_renamed(
    api: Api,
) -> None:
    """Scenario: 연락처 회사명이 바뀐 뒤에도 회사를 그대로 둔 날짜 수정은 저장된다."""
    # Given
    await given_logged_in_as(api)
    contact = await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    created = await given_meeting_by(api, kim, content="이전")
    renamed = await when_update_contact(
        api, contact["id"], update_payload("partner", company="새회사명", name=contact["name"])
    )
    then_status_is(renamed, 200)
    # When
    response = await when_update_meeting_as(
        api,
        kim,
        created["id"],
        meeting_item(content="이전", meeting_date="2027-05-20"),
    )
    # Then
    then_status_is(response, 200)
    assert response.json()["meeting_date"] == "2027-05-20"
    assert response.json()["partner_company"] == HANBIT
    assert "deal" not in response.json()


async def test_changing_to_another_registered_partner_company(api: Api) -> None:
    """Scenario: 다른 등록 파트너 회사로 바꾸면 그 회사의 대표 표기로 저장된다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    await given_partner(api, company="OtherPartners", contact="가나다")
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    created = await given_meeting_by(api, kim)
    # When
    response = await when_update_meeting_as(
        api, kim, created["id"], meeting_item(company="otherpartners")
    )
    # Then
    then_status_is(response, 200)
    assert response.json()["partner_company"] == "OtherPartners"
    listed = await when_list_meetings(api, partner="Other")
    assert len(listed.json()["items"]) == 1


async def test_changing_to_an_unregistered_company_is_rejected_at_the_company(api: Api) -> None:
    """Scenario: 등록되지 않은 회사로 바꾸면 partner_company 위치로 거절되고 기록은 그대로다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    created = await given_meeting_by(api, kim)
    # When
    response = await when_update_meeting_as(
        api, kim, created["id"], meeting_item(company="없는회사")
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_errors_are(response, [(("partner_company",), COMPANY_NOT_FOUND)])
    listed = await when_list_meetings(api)
    assert listed.json()["items"][0]["partner_company"] == HANBIT


async def test_an_update_body_with_deal_code_is_rejected(api: Api) -> None:
    """Scenario: 수정 본문에 deal_code가 있으면 request-validation 오류다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    created = await given_meeting_by(api, kim)
    # When
    response = await when_update_meeting_as(
        api, kim, created["id"], {**meeting_item(), "deal_code": "20261016-A001"}
    )
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_the_author_deletes_the_record(api: Api) -> None:
    """Scenario: 작성자가 지우면 204이고 목록에서 사라진다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    created = await given_meeting_by(
        api,
        kim,
    )
    # When
    response = await when_delete_meeting_as(api, kim, created["id"])
    # Then
    then_status_is(response, 204)
    await then_all_contents_are(api, [])


async def test_admin_deletes_another_users_record(api: Api) -> None:
    """Scenario: admin은 남의 기록도 지운다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    created = await given_meeting_by(
        api,
        kim,
    )
    # When
    response = await when_delete_meeting(api, created["id"])
    # Then
    then_status_is(response, 204)
    await then_all_contents_are(api, [])


async def test_another_sales_cannot_delete(api: Api) -> None:
    """Scenario: 다른 sales의 삭제는 403 안내 문구이고 기록이 남는다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    created = await given_meeting_by(api, kim, content="남아야 함")
    # When
    response = await when_delete_meeting_as(api, park, created["id"])
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == DELETE_FORBIDDEN
    await then_all_contents_are(api, ["남아야 함"])


async def test_a_read_only_user_cannot_delete(api: Api) -> None:
    """Scenario: 읽기 전용 사용자의 삭제는 403 읽기 전용 문구다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    viewer = await given_signed_in_session(api, login_id="viewer", role="user")
    created = await given_meeting_by(
        api,
        kim,
    )
    # When
    response = await when_delete_meeting_as(api, viewer, created["id"])
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == READ_ONLY


async def test_deleting_a_missing_record_is_404(api: Api) -> None:
    """Scenario: 없는 기록의 삭제는 404와 안내 문구다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_delete_meeting(api, MISSING_ID)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    assert response.json()["detail"] == NOT_FOUND


async def test_deleting_twice_is_404_the_second_time(api: Api) -> None:
    """Scenario: 같은 기록을 두 번 지우면 두 번째는 404다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    created = await given_meeting_by(
        api,
        kim,
    )
    await when_delete_meeting_as(api, kim, created["id"])
    # When
    response = await when_delete_meeting_as(api, kim, created["id"])
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


@pytest.mark.parametrize("bad_id", ["abc", "0", "-1"])
async def test_a_bad_meeting_id_is_a_request_validation_error(api: Api, bad_id: str) -> None:
    """Scenario: 정수가 아니거나 1보다 작은 id는 request-validation 오류다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_delete_meeting(api, bad_id)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
