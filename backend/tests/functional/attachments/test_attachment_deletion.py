"""Feature: 첨부 파일을 지운다.

판정 순서는 로그인(401) -> 읽기 전용 계정(403) -> 없는 첨부(404) -> 삭제 권한(403)이다.
admin은 모두, sales는 본인 파일과 퇴사한 sales의 파일을 지울 수 있다. 지우면 행과 디스크 파일이
사라지고 Deal History에 '삭제 <파일명>'이 남는다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.attachments import (
    DELETE_FORBIDDEN,
    NOT_FOUND,
    READ_ONLY,
    given_deal_with_files_enabled,
    given_disk_file_undeletable,
    given_file,
    then_attachment_history_is,
    then_attachment_is_unchanged,
    then_deal_updated_at_is_now,
    then_detail_is,
    then_disk_holds,
    then_listed_names_are,
    then_row_count_is,
    when_delete_attachment,
    when_get_attachment,
)
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.users import given_signed_in_session, given_user_deleted

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
UNKNOWN_ID = "6f1c1b3a-0000-4000-8000-000000000001"


async def test_the_uploader_deletes_their_own_file(api: Api) -> None:
    """Scenario: 업로더 본인이 지우면 204이고 목록·디스크에서 사라지며 이력이 남는다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    attachment = await given_file(api, code, session=kim, name="a.pdf", data=b"data")
    # When
    response = await when_delete_attachment(api, str(attachment["id"]), session=kim)
    # Then
    then_status_is(response, 204)
    assert response.content == b""
    then_problem_is(
        await when_get_attachment(api, str(attachment["id"])), status=404, type_suffix="not-found"
    )
    await then_listed_names_are(api, code, [])
    then_disk_holds(api, code, [])
    await then_attachment_history_is(api, code, [("", "업로드 a.pdf"), ("", "삭제 a.pdf")])
    await then_deal_updated_at_is_now(api, code)


async def test_only_the_named_file_is_deleted(api: Api) -> None:
    """Scenario: 한 파일을 지워도 같은 Deal의 다른 파일은 그대로다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    gone = await given_file(api, code, name="gone.pdf", data=b"1")
    await given_file(api, code, name="kept.pdf", data=b"2")
    # When
    response = await when_delete_attachment(api, str(gone["id"]))
    # Then
    then_status_is(response, 204)
    await then_listed_names_are(api, code, ["kept.pdf"])
    then_disk_holds(api, code, [b"2"])


async def test_another_sales_cannot_delete_a_file_they_did_not_upload(api: Api) -> None:
    """Scenario: 다른 sales의 삭제는 403이고 파일·행·이력이 그대로다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    attachment = await given_file(api, code, session=kim, name="a.pdf", data=b"keep")
    # When
    response = await when_delete_attachment(api, str(attachment["id"]), session=park)
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    then_detail_is(response, DELETE_FORBIDDEN)
    await then_attachment_is_unchanged(api, attachment)
    then_disk_holds(api, code, [b"keep"])
    await then_attachment_history_is(api, code, [("", "업로드 a.pdf")])


async def test_sales_can_delete_a_file_after_its_sales_uploader_resigned(api: Api) -> None:
    """Scenario: 업로더(sales)가 퇴사하면 다른 sales가 그 파일을 지울 수 있다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    attachment = await given_file(api, code, session=kim, name="a.pdf")
    await given_user_deleted(api, str(attachment["uploaded_by"]["id"]))
    # When
    response = await when_delete_attachment(api, str(attachment["id"]), session=park)
    # Then
    then_status_is(response, 204)
    then_disk_holds(api, code, [])


async def test_sales_cannot_delete_a_file_uploaded_by_an_admin_even_after_the_admin_resigned(
    api: Api,
) -> None:
    """Scenario: 퇴사한 admin의 파일은 sales가 지울 수 없다(퇴사한 sales의 파일만 가능)."""
    # Given
    code = await given_deal_with_files_enabled(api)
    boss = await given_signed_in_session(api, login_id="boss", role="admin")
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    attachment = await given_file(api, code, session=boss, name="a.pdf", data=b"admin's")
    await given_user_deleted(api, str(attachment["uploaded_by"]["id"]))
    # When
    response = await when_delete_attachment(api, str(attachment["id"]), session=kim)
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    then_detail_is(response, DELETE_FORBIDDEN)
    then_disk_holds(api, code, [b"admin's"])


async def test_an_admin_deletes_any_file(api: Api) -> None:
    """Scenario: admin은 남의 파일도 지울 수 있다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    attachment = await given_file(api, code, session=kim, name="a.pdf")
    # When
    response = await when_delete_attachment(api, str(attachment["id"]))
    # Then
    then_status_is(response, 204)
    await then_row_count_is(api, code, 0)
    await then_attachment_history_is(api, code, [("", "업로드 a.pdf"), ("", "삭제 a.pdf")])


async def test_a_read_only_user_cannot_delete_and_is_refused_before_the_lookup(api: Api) -> None:
    """Scenario: 조회 전용(user)은 403(읽기 전용 문구)이고, 없는 id여도 404보다 403이 먼저다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    attachment = await given_file(api, code, name="a.pdf", data=b"keep")
    viewer = await given_signed_in_session(api, login_id="viewer", role="user")
    # When
    existing = await when_delete_attachment(api, str(attachment["id"]), session=viewer)
    missing = await when_delete_attachment(api, UNKNOWN_ID, session=viewer)
    # Then
    for refused in (existing, missing):
        then_problem_is(refused, status=403, type_suffix="forbidden")
        then_detail_is(refused, READ_ONLY)
    then_disk_holds(api, code, [b"keep"])


async def test_deleting_an_unknown_attachment_is_not_found(api: Api) -> None:
    """Scenario: 없는 첨부를 지우면 404다."""
    # Given
    await given_deal_with_files_enabled(api)
    # When
    response = await when_delete_attachment(api, UNKNOWN_ID)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    then_detail_is(response, NOT_FOUND)


async def test_an_anonymous_visitor_cannot_delete(api: Api) -> None:
    """Scenario: 로그인하지 않으면 지울 수 없다(401)."""
    # Given
    code = await given_deal_with_files_enabled(api)
    attachment = await given_file(api, code, name="a.pdf")
    api.forget_session()
    # When
    response = await when_delete_attachment(api, str(attachment["id"]))
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_the_row_is_deleted_even_when_the_disk_file_cannot_be_removed(api: Api) -> None:
    """Scenario: 디스크 파일을 지우지 못해도 204이고 행은 사라진다(경고 로그만 남는다)."""
    # Given
    code = await given_deal_with_files_enabled(api)
    attachment = await given_file(api, code, name="a.pdf")
    given_disk_file_undeletable(api, code)
    # When
    response = await when_delete_attachment(api, str(attachment["id"]))
    # Then
    then_status_is(response, 204)
    await then_row_count_is(api, code, 0)
    await then_attachment_history_is(api, code, [("", "업로드 a.pdf"), ("", "삭제 a.pdf")])
