"""Feature: 로그인한 누구나 Deal의 첨부 목록을 보고 내려받는다.

목록은 업로드 시각 최신순이고, 다운로드는 저장한 바이트 그대로 `application/octet-stream` + 첨부
(attachment) + 원본 파일 이름으로 내려준다. 파일을 못 찾거나 저장 위치를 못 쓰면 구분된 오류를 낸다.
"""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.attachments import (
    ATTACHMENT_KEYS,
    CONTENT_MISSING,
    DEAL_NOT_FOUND,
    DOWNLOAD_UNAVAILABLE,
    NOT_FOUND,
    OCTET_STREAM,
    given_deal_with_files_enabled,
    given_disk_file_removed,
    given_disk_file_unreadable,
    given_file,
    given_storage_location_moved,
    given_storage_location_removed,
    then_detail_is,
    then_listed_names_are,
    when_download,
    when_get_attachment,
    when_list_attachments,
)
from tests.functional.steps.auth import RoleName, storage_path_of
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.users import given_signed_in_session

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
ROLES = ["admin", "sales", "user"]
UNKNOWN_ID = "6f1c1b3a-0000-4000-8000-000000000001"


@pytest.mark.parametrize("role", ROLES)
async def test_everyone_lists_the_attachments_newest_first(api: Api, role: RoleName) -> None:
    """Scenario: 어떤 역할이든 첨부 목록을 최신순으로 본다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    await given_file(api, code, name="first.pdf")
    await given_file(api, code, name="second.pdf")
    reader = await given_signed_in_session(api, login_id=f"{role}-reader", role=role)
    # When
    response = await when_list_attachments(api, code, session=reader)
    # Then
    then_status_is(response, 200)
    assert [item["file_name"] for item in response.json()["items"]] == ["second.pdf", "first.pdf"]
    assert set(response.json()["items"][0]) == ATTACHMENT_KEYS


async def test_a_deal_without_files_has_an_empty_list(api: Api) -> None:
    """Scenario: 첨부가 없으면 빈 목록이다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await when_list_attachments(api, code)
    # Then
    then_status_is(response, 200)
    assert response.json() == {"items": []}


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code"])
async def test_the_list_of_a_missing_deal_is_not_found(api: Api, code: str) -> None:
    """Scenario: 없는 Deal이나 형식이 틀린 code의 목록은 404다."""
    # Given
    await given_deal_with_files_enabled(api)
    # When
    response = await when_list_attachments(api, code)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    then_detail_is(response, DEAL_NOT_FOUND)


async def test_one_attachment_can_be_read_by_id(api: Api) -> None:
    """Scenario: id로 첨부 한 건을 읽는다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    attachment = await given_file(api, code, name="a.pdf", data=b"12345", description="설명")
    # When
    response = await when_get_attachment(api, str(attachment["id"]))
    # Then
    then_status_is(response, 200)
    assert response.json() == attachment


async def test_an_unknown_attachment_is_not_found(api: Api) -> None:
    """Scenario: 없는 id의 단건 조회와 다운로드는 404다."""
    # Given
    await given_deal_with_files_enabled(api)
    # When
    single = await when_get_attachment(api, UNKNOWN_ID)
    download = await when_download(api, UNKNOWN_ID)
    # Then
    for response in (single, download):
        then_problem_is(response, status=404, type_suffix="not-found")
        then_detail_is(response, NOT_FOUND)


@pytest.mark.parametrize("role", ROLES)
async def test_everyone_downloads_the_exact_bytes(api: Api, role: RoleName) -> None:
    """Scenario: 어떤 역할이든 저장한 바이트 그대로 내려받고, 형식은 octet-stream 첨부다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    data = b"%PDF \x00\x01\x02 binary \xff" * 50
    attachment = await given_file(api, code, name="report.pdf", data=data)
    reader = await given_signed_in_session(api, login_id=f"{role}-reader", role=role)
    # When
    response = await when_download(api, str(attachment["id"]), session=reader)
    # Then
    then_status_is(response, 200)
    assert response.content == data
    assert response.headers["content-type"].split(";")[0] == OCTET_STREAM
    assert response.headers["content-length"] == str(len(data))
    assert response.headers["content-disposition"] == (
        "attachment; filename=\"report.pdf\"; filename*=UTF-8''report.pdf"
    )


async def test_download_keeps_the_korean_file_name(api: Api) -> None:
    """Scenario: 한글 이름은 filename*(UTF-8 퍼센트 인코딩)로 원본 그대로 내려간다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    attachment = await given_file(api, code, name="견적서 최종.pdf")
    # When
    response = await when_download(api, str(attachment["id"]))
    # Then
    then_status_is(response, 200)
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment; ")
    assert disposition.endswith(
        "filename*=UTF-8''%EA%B2%AC%EC%A0%81%EC%84%9C%20%EC%B5%9C%EC%A2%85.pdf"
    )


async def test_download_never_uses_the_uploaded_content_type(api: Api) -> None:
    """Scenario: html로 올려도 브라우저 안에서 열리지 않도록 octet-stream 첨부로 내려간다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    attachment = await given_file(
        api, code, name="page.html", data=b"<script>1</script>", mime="text/html"
    )
    # When
    response = await when_download(api, str(attachment["id"]))
    # Then
    assert response.headers["content-type"].split(";")[0] == OCTET_STREAM
    assert response.headers["content-disposition"].startswith("attachment;")
    assert (await when_get_attachment(api, str(attachment["id"]))).json()["mime"] == "text/html"


async def test_a_large_file_downloads_intact_in_several_chunks(api: Api) -> None:
    """Scenario: 여러 청크로 흘려 보내는 큰 파일도 바이트와 길이가 그대로다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    data = bytes(range(256)) * (3 * 1024 * 4)  # 3 MiB
    attachment = await given_file(api, code, name="big.bin", data=data)
    # When
    response = await when_download(api, str(attachment["id"]))
    # Then
    assert response.content == data
    assert response.headers["content-length"] == str(len(data))


async def test_an_empty_file_downloads_as_empty(api: Api) -> None:
    """Scenario: 0바이트 파일도 내려받을 수 있다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    attachment = await given_file(api, code, name="empty.txt", data=b"")
    # When
    response = await when_download(api, str(attachment["id"]))
    # Then
    assert (response.status_code, response.content) == (200, b"")


async def test_a_row_without_its_disk_file_is_reported_as_missing_content(api: Api) -> None:
    """Scenario: 행은 있는데 디스크 파일이 없으면 404와 '내용을 찾을 수 없습니다' 안내다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    attachment = await given_file(api, code)
    given_disk_file_removed(api, code)
    # When
    response = await when_download(api, str(attachment["id"]))
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    then_detail_is(response, CONTENT_MISSING)


async def test_files_are_looked_up_under_the_current_storage_location(api: Api) -> None:
    """Scenario: 저장 위치를 바꾸면 옮기기 전 파일은 404 안내가 되고 목록·단건은 그대로 보인다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    attachment = await given_file(api, code, name="a.pdf")
    await given_storage_location_moved(api, str(Path(storage_path_of(api)).parent / "elsewhere"))
    # When
    response = await when_download(api, str(attachment["id"]))
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    then_detail_is(response, CONTENT_MISSING)
    await then_listed_names_are(api, code, ["a.pdf"])


async def test_a_file_that_cannot_be_read_is_unavailable_not_missing(api: Api) -> None:
    """Scenario: 파일이 있지만 읽을 수 없으면 '없음'(404)이 아니라 503(storage-unavailable)이다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    attachment = await given_file(api, code)
    given_disk_file_unreadable(api, code)
    # When
    response = await when_download(api, str(attachment["id"]))
    # Then
    then_problem_is(response, status=503, type_suffix="storage-unavailable")
    then_detail_is(response, DOWNLOAD_UNAVAILABLE)


async def test_without_a_storage_location_the_download_is_unavailable(api: Api) -> None:
    """Scenario: 저장 위치 설정이 없으면 다운로드는 503이지만 목록과 단건은 읽힌다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    attachment = await given_file(api, code, name="a.pdf")
    await given_storage_location_removed(api)
    # When
    response = await when_download(api, str(attachment["id"]))
    # Then
    then_problem_is(response, status=503, type_suffix="storage-unavailable")
    then_detail_is(response, DOWNLOAD_UNAVAILABLE)
    await then_listed_names_are(api, code, ["a.pdf"])
