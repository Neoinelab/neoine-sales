"""첨부 업로드 라우터(P2b AC-07~11, 7.1·7.3): multipart 요청, 201/200 응답, 오류 매핑, 권한.

FakeUseCases·FakeFileStorage 위에서 HTTP 계약을 확인한다. 같은 이름 판정과 권한 규칙 자체는
유스케이스 단위 테스트가, 실제 DB·디스크는 functional이 맡는다.
"""

import pytest

from app.application.storage.errors import UPLOAD_UNAVAILABLE
from app.domain.attachment.values import (
    DESCRIPTION_TOO_LONG,
    FILE_TOO_LARGE,
    INVALID_FILE_NAME,
    MAX_FILE_BYTES,
    NO_FILE,
    blocked_message,
)
from app.domain.auth.principal import Role
from tests.unit.web.attachment_http import (
    ATTACHMENT_KEYS,
    DEAL_CODE,
    READ_ONLY,
    UPLOAD_KEYS,
    UPLOAD_URL,
    client_for,
    form,
    problem,
    ready_use_cases,
    upload,
)


async def test_a_new_file_is_201_with_a_location_and_the_attachment() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        response = await upload(
            http, ("견적서.pdf", b"%PDF bytes", "application/pdf"), description=" 최종 "
        )

    assert response.status_code == 201, response.text
    body = response.json()
    attachment = body["attachment"]
    assert set(body) == UPLOAD_KEYS
    assert body["outcome"] == "uploaded"
    assert set(attachment) == ATTACHMENT_KEYS
    assert response.headers["location"] == f"/api/v1/attachments/{attachment['id']}"
    assert (attachment["file_name"], attachment["description"]) == ("견적서.pdf", "최종")
    assert (attachment["size"], attachment["mime"]) == (10, "application/pdf")
    assert attachment["deal_code"] == DEAL_CODE
    assert attachment["uploaded_by"]["name"] == "사용자 kim"
    assert set(attachment["uploaded_by"]) == {"id", "name", "resigned", "label", "role"}
    assert attachment["uploaded_at"]


async def test_the_bytes_land_in_the_storage_and_the_client_content_type_is_kept() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        response = await upload(http, ("notes.txt", b"plain text", "text/plain"))

    assert response.json()["attachment"]["mime"] == "text/plain"
    assert use_cases.file_storage.file_count() == 1
    (stored,) = use_cases.file_storage._files.values()
    assert stored == b"plain text"


async def test_description_and_on_exists_are_optional() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        response = await http.post(UPLOAD_URL, files=form(("a.pdf", b"x", "application/pdf")))

    assert response.status_code == 201, response.text
    assert response.json()["attachment"]["description"] == ""


async def test_an_empty_file_is_accepted() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        response = await upload(http, ("empty.txt", b"", "text/plain"))

    assert response.status_code == 201, response.text
    assert response.json()["attachment"]["size"] == 0


async def test_the_same_name_with_ask_is_409_file_exists() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        await upload(http)
        response = await upload(http, on_exists="ask")

    body = problem(response, 409, "file-exists")
    assert body["title"] == "File Exists"
    assert body["detail"] == "같은 이름의 파일이 이미 있습니다: a.pdf"
    assert use_cases.file_storage.file_count() == 1


async def test_the_same_name_with_skip_is_200_skipped_without_an_attachment() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        await upload(http)
        response = await upload(http, on_exists="skip")

    assert response.status_code == 200, response.text
    assert response.json() == {"outcome": "skipped", "attachment": None}
    assert "location" not in response.headers


async def test_the_same_name_with_replace_is_200_replaced_and_keeps_the_id() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        first = (await upload(http)).json()["attachment"]
        response = await upload(
            http, ("a.pdf", b"newer content", "application/pdf"), on_exists="replace"
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "replaced"
    assert body["attachment"]["id"] == first["id"]
    assert body["attachment"]["size"] == 13


async def test_replace_by_another_sales_is_403_with_the_replace_sentence() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases, login="kim") as kim:
        await upload(kim)
    async with client_for(use_cases, login="park") as park:
        response = await upload(
            park, ("a.pdf", b"mine now", "application/pdf"), on_exists="replace"
        )

    assert problem(response, 403, "forbidden")["detail"] == "본인이 올린 파일만 교체할 수 있습니다."


async def test_an_admin_can_replace_anyones_file() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases, login="kim") as kim:
        await upload(kim)
    async with client_for(use_cases, login="boss", role=Role.ADMIN) as boss:
        response = await upload(boss, ("a.pdf", b"admin", "application/pdf"), on_exists="replace")

    assert response.status_code == 200, response.text
    assert response.json()["attachment"]["uploaded_by"]["name"] == "사용자 boss"


@pytest.mark.parametrize(
    ("file", "fields", "detail"),
    [
        pytest.param(None, {}, NO_FILE, id="no-file-part"),
        pytest.param(("", b"", "application/octet-stream"), {}, NO_FILE, id="empty-file-name"),
        pytest.param(
            ("a.pdf", b"x", "x/y"), {"description": "가" * 101}, DESCRIPTION_TOO_LONG, id="desc"
        ),
        pytest.param(("setup.EXE", b"x", "x/y"), {}, blocked_message("exe"), id="blocked"),
        pytest.param((".", b"x", "x/y"), {}, INVALID_FILE_NAME, id="dot-name"),
    ],
)
async def test_invalid_uploads_are_422_invalid_value_with_the_documented_sentence(
    file: tuple[str, bytes, str] | None,
    fields: dict[str, str],
    detail: str,
) -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        response = await http.post(UPLOAD_URL, files=form(file, **fields))

    assert problem(response, 422, "invalid-value")["detail"] == detail
    assert use_cases.file_storage.file_count() == 0


async def test_a_file_over_100mb_is_422_before_anything_is_stored() -> None:
    use_cases = await ready_use_cases()
    too_big = ("big.bin", bytes(MAX_FILE_BYTES + 1), "application/octet-stream")
    async with client_for(use_cases) as http:
        response = await upload(http, too_big)

    assert problem(response, 422, "invalid-value")["detail"] == FILE_TOO_LARGE
    assert use_cases.file_storage.file_count() == 0


async def test_an_unknown_on_exists_value_is_a_request_validation_error() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        response = await upload(http, on_exists="overwrite")

    problem(response, 422, "request-validation")
    assert use_cases.file_storage.file_count() == 0


async def test_a_json_body_instead_of_multipart_is_a_validation_error_not_a_server_error() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        response = await http.post(UPLOAD_URL, json={"description": "x"})

    assert response.status_code in {415, 422}, response.text
    assert use_cases.file_storage.file_count() == 0


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code"])
async def test_a_missing_or_malformed_deal_is_404_before_the_file_is_checked(code: str) -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        response = await http.post(f"/api/v1/deals/{code}/attachments", files=form(None))

    assert problem(response, 404, "not-found")["detail"] == "Deal을 찾을 수 없습니다."


async def test_a_read_only_user_is_403_even_for_a_missing_deal() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases, login="viewer", role=Role.USER) as http:
        existing = await upload(http)
        missing = await http.post("/api/v1/deals/20991231-ZZZZ/attachments", files=form())

    for response in (existing, missing):
        assert problem(response, 403, "forbidden")["detail"] == READ_ONLY
    assert use_cases.file_storage.file_count() == 0


async def test_an_anonymous_request_is_401() -> None:
    use_cases = await ready_use_cases()
    async with client_for(use_cases, login=None) as http:
        response = await upload(http)

    problem(response, 401, "unauthenticated")
    assert use_cases.file_storage.file_count() == 0


async def test_without_a_storage_location_the_upload_is_503_storage_unavailable() -> None:
    use_cases = await ready_use_cases(storage=False)
    async with client_for(use_cases) as http:
        response = await upload(http)

    body = problem(response, 503, "storage-unavailable")
    assert body["detail"] == UPLOAD_UNAVAILABLE
    assert body["title"] == "Storage Unavailable"


async def test_a_storage_location_that_cannot_be_written_is_503_storage_unavailable() -> None:
    use_cases = await ready_use_cases()
    use_cases.file_storage.block("/data")
    async with client_for(use_cases) as http:
        response = await upload(http)

    assert problem(response, 503, "storage-unavailable")["detail"] == UPLOAD_UNAVAILABLE
