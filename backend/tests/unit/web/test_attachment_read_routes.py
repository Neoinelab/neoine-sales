"""첨부 조회·다운로드·삭제 라우터(P2b AC-12~14, 7.1): 목록, 단건, 다운로드 헤더, 삭제 판정 순서.

FakeUseCases·FakeFileStorage 위에서 HTTP 계약을 확인한다. 실제 DB·디스크는 functional이 맡는다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.storage.errors import DOWNLOAD_UNAVAILABLE
from app.domain.auth.principal import Role
from tests.unit.web.attachment_http import (
    ATTACHMENT_KEYS,
    DEAL_CODE,
    READ_ONLY,
    UPLOAD_URL,
    client_for,
    problem,
    ready_use_cases,
    upload,
)

if TYPE_CHECKING:
    from tests.fakes.use_cases import FakeUseCases

NOT_FOUND = "첨부 파일을 찾을 수 없습니다."
CONTENT_MISSING = "첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요."
MISSING_ID = "6f1c1b3a-0000-4000-8000-000000000001"


async def _uploaded_id(
    use_cases: FakeUseCases,
    name: str = "a.pdf",
    data: bytes = b"hello",
    mime: str = "application/pdf",
    login: str = "kim",
) -> str:
    async with client_for(use_cases, login=login) as http:
        response = await upload(http, (name, data, mime))
    return str(response.json()["attachment"]["id"])


async def test_the_list_is_newest_first_and_open_to_every_role() -> None:
    use_cases = await ready_use_cases()
    first = await _uploaded_id(use_cases, "first.pdf")
    second = await _uploaded_id(use_cases, "second.pdf")

    for role in (Role.ADMIN, Role.SALES, Role.USER):
        async with client_for(use_cases, login=f"{role.value}-reader", role=role) as http:
            response = await http.get(UPLOAD_URL)

        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == {"items"}
        assert [item["id"] for item in body["items"]] == [second, first]
        assert set(body["items"][0]) == ATTACHMENT_KEYS


async def test_the_list_of_a_deal_without_files_is_empty() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        response = await http.get(UPLOAD_URL)

    assert response.json() == {"items": []}


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code"])
async def test_the_list_of_a_missing_or_malformed_deal_is_404(code: str) -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        response = await http.get(f"/api/v1/deals/{code}/attachments")

    assert problem(response, 404, "not-found")["detail"] == "Deal을 찾을 수 없습니다."


async def test_the_list_needs_a_login() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases, login=None) as http:
        response = await http.get(UPLOAD_URL)

    problem(response, 401, "unauthenticated")


async def test_one_attachment_is_readable_by_a_read_only_user() -> None:
    use_cases = await ready_use_cases()
    attachment_id = await _uploaded_id(use_cases, "a.pdf", b"12345")
    async with client_for(use_cases, login="viewer", role=Role.USER) as http:
        response = await http.get(f"/api/v1/attachments/{attachment_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == ATTACHMENT_KEYS
    assert (body["id"], body["file_name"], body["size"], body["deal_code"]) == (
        attachment_id,
        "a.pdf",
        5,
        DEAL_CODE,
    )


async def test_an_unknown_attachment_is_404_with_its_sentence() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        single = await http.get(f"/api/v1/attachments/{MISSING_ID}")
        download = await http.get(f"/api/v1/attachments/{MISSING_ID}/download")

    for response in (single, download):
        assert problem(response, 404, "not-found")["detail"] == NOT_FOUND


async def test_download_streams_the_bytes_as_an_octet_stream_attachment() -> None:
    use_cases = await ready_use_cases()
    data = b"\x00\x01binary\xff" * 1000
    attachment_id = await _uploaded_id(use_cases, "report.pdf", data)
    async with client_for(use_cases, login="viewer", role=Role.USER) as http:
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    assert response.status_code == 200, response.text
    assert response.content == data
    assert response.headers["content-type"].split(";")[0] == "application/octet-stream"
    assert response.headers["content-length"] == str(len(data))
    assert response.headers["content-disposition"] == (
        "attachment; filename=\"report.pdf\"; filename*=UTF-8''report.pdf"
    )


async def test_download_never_serves_the_clients_content_type() -> None:
    use_cases = await ready_use_cases()
    attachment_id = await _uploaded_id(
        use_cases, "page.html", b"<script>alert(1)</script>", "text/html"
    )
    async with client_for(use_cases) as http:
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    assert response.headers["content-type"].split(";")[0] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment;")


async def test_download_keeps_a_korean_file_name_in_the_utf8_parameter() -> None:
    use_cases = await ready_use_cases()
    attachment_id = await _uploaded_id(use_cases, "견적서.pdf")
    async with client_for(use_cases) as http:
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    assert response.headers["content-disposition"] == (
        "attachment; filename=\"___.pdf\"; filename*=UTF-8''%EA%B2%AC%EC%A0%81%EC%84%9C.pdf"
    )


async def test_download_of_an_empty_file_has_zero_length() -> None:
    use_cases = await ready_use_cases()
    attachment_id = await _uploaded_id(use_cases, "empty.txt", b"")
    async with client_for(use_cases) as http:
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    assert (response.status_code, response.content) == (200, b"")
    assert response.headers["content-length"] == "0"


async def test_download_of_a_row_whose_file_is_gone_is_404_with_the_content_sentence() -> None:
    use_cases = await ready_use_cases()
    attachment_id = await _uploaded_id(use_cases)
    use_cases.file_storage._files.clear()
    async with client_for(use_cases) as http:
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    assert problem(response, 404, "not-found")["detail"] == CONTENT_MISSING


async def test_download_without_a_storage_location_is_503() -> None:
    use_cases = await ready_use_cases()
    attachment_id = await _uploaded_id(use_cases)
    use_cases.uow.storage_settings._items.clear()
    async with client_for(use_cases) as http:
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    assert problem(response, 503, "storage-unavailable")["detail"] == DOWNLOAD_UNAVAILABLE


async def test_download_of_a_file_that_cannot_be_read_is_503_not_404() -> None:
    use_cases = await ready_use_cases()
    attachment_id = await _uploaded_id(use_cases)
    use_cases.file_storage.fail_reads = True
    async with client_for(use_cases) as http:
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    assert problem(response, 503, "storage-unavailable")["detail"] == DOWNLOAD_UNAVAILABLE


async def test_the_uploader_deletes_the_file_with_204() -> None:
    use_cases = await ready_use_cases()
    attachment_id = await _uploaded_id(use_cases)
    async with client_for(use_cases) as http:
        response = await http.delete(f"/api/v1/attachments/{attachment_id}")
        again = await http.get(f"/api/v1/attachments/{attachment_id}")

    assert (response.status_code, response.content) == (204, b"")
    problem(again, 404, "not-found")
    assert use_cases.file_storage.file_count() == 0


async def test_another_sales_is_403_and_an_admin_is_204() -> None:
    use_cases = await ready_use_cases()
    attachment_id = await _uploaded_id(use_cases)
    async with client_for(use_cases, login="park") as park:
        denied = await park.delete(f"/api/v1/attachments/{attachment_id}")
    async with client_for(use_cases, login="boss", role=Role.ADMIN) as boss:
        allowed = await boss.delete(f"/api/v1/attachments/{attachment_id}")

    assert problem(denied, 403, "forbidden")["detail"] == "본인이 올린 파일만 삭제할 수 있습니다."
    assert allowed.status_code == 204


async def test_a_read_only_user_is_403_before_the_file_is_looked_up() -> None:
    use_cases = await ready_use_cases()
    attachment_id = await _uploaded_id(use_cases)
    async with client_for(use_cases, login="viewer", role=Role.USER) as http:
        existing = await http.delete(f"/api/v1/attachments/{attachment_id}")
        missing = await http.delete(f"/api/v1/attachments/{uuid4()}")

    for response in (existing, missing):
        assert problem(response, 403, "forbidden")["detail"] == READ_ONLY
    assert use_cases.file_storage.file_count() == 1


async def test_deleting_an_unknown_attachment_is_404() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        response = await http.delete(f"/api/v1/attachments/{MISSING_ID}")

    assert problem(response, 404, "not-found")["detail"] == NOT_FOUND


async def test_deleting_needs_a_login() -> None:
    use_cases = await ready_use_cases()
    attachment_id = await _uploaded_id(use_cases)
    async with client_for(use_cases, login=None) as anonymous:
        response = await anonymous.delete(f"/api/v1/attachments/{attachment_id}")

    problem(response, 401, "unauthenticated")
