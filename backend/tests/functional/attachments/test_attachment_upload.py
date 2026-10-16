"""Feature: 영업은 Deal 상세에서 파일을 올린다.

sales·admin이 파일(과 100자 이내 설명)을 올리면 저장 위치의 Deal 디렉터리에 그대로 저장되고,
첨부 목록과 Deal History(첨부 파일)에 남으며 Deal 수정 시각이 바뀐다. 조회 전용(user)은 올릴 수
없고, 저장 위치를 없으면 아무것도 저장되지 않는다.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.attachments import (
    DEAL_NOT_FOUND,
    READ_ONLY,
    UPLOAD_UNAVAILABLE,
    given_deal_with_files_enabled,
    given_storage_location_removed,
    then_attachment_history_is,
    then_deal_updated_at_is_now,
    then_detail_is,
    then_disk_holds,
    then_listed_names_are,
    then_row_count_is,
    then_stored_file_is_named_by_a_key,
    then_upload_is,
    when_upload,
)
from tests.functional.steps.common import then_problem_is
from tests.functional.steps.login_db import sql_rows
from tests.functional.steps.storage import given_storage_blocked_by_a_file
from tests.functional.steps.users import given_signed_in_session
from tests.support.functional_clock import active_clock

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

PDF = b"%PDF-1.7\n\x00\x01 binary \xff\xfe bytes"


async def test_sales_uploads_a_file_with_a_description(api: Api) -> None:
    """Scenario: sales가 설명과 함께 파일을 올리면 201이고 파일이 저장 위치에 그대로 저장된다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    # When
    response = await when_upload(
        api, code, session=kim, name="견적서.pdf", data=PDF, description="  최종본  "
    )
    # Then
    attachment = then_upload_is(response, status=201, outcome="uploaded", name="견적서.pdf")
    assert attachment is not None
    assert response.headers["location"] == f"/api/v1/attachments/{attachment['id']}"
    assert (attachment["description"], attachment["size"]) == ("최종본", len(PDF))
    assert attachment["mime"] == "application/pdf"
    assert attachment["deal_code"] == code
    assert attachment["uploaded_by"]["label"] == "사용자 kim"
    assert datetime.fromisoformat(attachment["uploaded_at"]) == active_clock().now()
    then_disk_holds(api, code, [PDF])
    then_stored_file_is_named_by_a_key(api, code, "견적서.pdf")
    await then_listed_names_are(api, code, ["견적서.pdf"])


async def test_an_admin_uploads_too_and_the_description_is_optional(api: Api) -> None:
    """Scenario: admin도 올릴 수 있고 설명을 생략하면 빈 설명이다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await when_upload(api, code, name="memo.txt", data=b"hi", mime="text/plain")
    # Then
    attachment = then_upload_is(response, status=201, outcome="uploaded", name="memo.txt")
    assert attachment is not None
    assert attachment["description"] == ""
    assert attachment["mime"] == "text/plain"


async def test_the_upload_is_recorded_in_the_deal_history_and_touches_the_deal(api: Api) -> None:
    """Scenario: 업로드하면 Deal History에 '업로드 <파일명>'이 남고 Deal 수정 시각이 바뀐다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await when_upload(api, code, name="a.pdf")
    # Then
    then_upload_is(response, status=201, outcome="uploaded")
    await then_attachment_history_is(api, code, [("", "업로드 a.pdf")])
    await then_deal_updated_at_is_now(api, code)


@pytest.mark.parametrize(
    ("name", "data", "description"),
    [
        ("a.tar.gz", b"x", ""),
        ("README", b"x", ""),
        ("empty.txt", b"", ""),
        ("exe.txt", b"x", ""),
        ("a.exe.txt", b"x", ""),
        ("긴 설명.txt", b"x", "😀" * 100),
        pytest.param("n" * 251 + ".pdf", b"x", "", id="name-255-chars"),
    ],
)
async def test_boundary_uploads_are_accepted(
    api: Api, name: str, data: bytes, description: str
) -> None:
    """Scenario: 확장자 없는 이름, 이중 확장자, 0바이트, 설명 100자, 이름 255자는 올릴 수 있다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await when_upload(api, code, name=name, data=data, description=description)
    # Then
    attachment = then_upload_is(response, status=201, outcome="uploaded", name=name)
    assert attachment is not None
    assert attachment["size"] == len(data)
    then_disk_holds(api, code, [data])


async def test_a_read_only_user_cannot_upload(api: Api) -> None:
    """Scenario: 조회 전용(user)은 올릴 수 없다. 없는 Deal에도 403이 먼저다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    viewer = await given_signed_in_session(api, login_id="viewer", role="user")
    # When
    response = await when_upload(api, code, session=viewer)
    missing = await when_upload(api, "20991231-ZZZZ", session=viewer)
    # Then
    for refused in (response, missing):
        then_problem_is(refused, status=403, type_suffix="forbidden")
        then_detail_is(refused, READ_ONLY)
    then_disk_holds(api, code, [])
    await then_row_count_is(api, code, 0)


async def test_an_anonymous_visitor_cannot_upload(api: Api) -> None:
    """Scenario: 로그인하지 않으면 올릴 수 없다(401)."""
    # Given
    code = await given_deal_with_files_enabled(api)
    api.forget_session()
    # When
    response = await when_upload(api, code)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")
    then_disk_holds(api, code, [])


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code"])
async def test_uploading_to_a_missing_deal_is_not_found(api: Api, code: str) -> None:
    """Scenario: 없는 Deal이나 형식이 틀린 code에는 올릴 수 없다(404)."""
    # Given
    await given_deal_with_files_enabled(api)
    # When
    response = await when_upload(api, code)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    then_detail_is(response, DEAL_NOT_FOUND)


async def test_without_a_storage_location_nothing_is_stored(api: Api) -> None:
    """Scenario: 저장 위치 설정이 없으면 503(storage-unavailable)이고 행·이력·파일이 남지 않는다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    await given_storage_location_removed(api)
    # When
    response = await when_upload(api, code, name="a.pdf")
    # Then
    then_problem_is(response, status=503, type_suffix="storage-unavailable")
    then_detail_is(response, UPLOAD_UNAVAILABLE)
    await then_row_count_is(api, code, 0)
    await then_attachment_history_is(api, code, [])
    then_disk_holds(api, code, [])


async def test_a_storage_location_that_cannot_be_written_stores_nothing(api: Api) -> None:
    """Scenario: 저장 위치에 쓸 수 없으면 503이고 아무것도 남지 않는다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    blocked = given_storage_blocked_by_a_file(api)
    await sql_rows(api, "update storage_settings set path = :path", path=blocked)
    # When
    response = await when_upload(api, code, name="a.pdf")
    # Then
    then_problem_is(response, status=503, type_suffix="storage-unavailable")
    then_detail_is(response, UPLOAD_UNAVAILABLE)
    await then_row_count_is(api, code, 0)
    await then_attachment_history_is(api, code, [])


async def test_uploaded_files_are_listed_newest_first(api: Api) -> None:
    """Scenario: 올린 파일은 첨부 목록에서 최신순으로 바로 보인다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    await when_upload(api, code, name="first.pdf")
    # When
    response = await when_upload(api, code, name="second.pdf")
    # Then
    then_upload_is(response, status=201, outcome="uploaded", name="second.pdf")
    await then_listed_names_are(api, code, ["second.pdf", "first.pdf"])
