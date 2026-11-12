"""첨부 업로드 라우터(7.1·7.3): multipart 요청, 201/200 응답, 오류 매핑, 권한.

FakeUseCases·FakeFileStorage 위에서 HTTP 계약을 확인한다. 같은 이름 판정과 권한 규칙 자체는
유스케이스 단위 테스트가, 실제 DB·디스크는 infra 단위 테스트가 맡는다.
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
    """새 파일 업로드는 201과 Location, 첨부 응답을 돌려준다.

    테스트 코드: AT-001
    """
    # given: 저장 위치가 설정된 Deal과 로그인한 sales
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        # when: multipart로 PDF와 설명을 올린다
        response = await upload(
            http, ("견적서.pdf", b"%PDF bytes", "application/pdf"), description=" 최종 "
        )

    # then: 201 uploaded, Location은 단건 주소이고 이름·설명·크기·mime·Deal·업로더가 기대대로다
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
    """올린 바이트가 저장소에 그대로 저장되고 클라이언트의 Content-Type이 mime이 된다.

    테스트 코드: AT-001
    """
    # given: 저장 위치가 설정된 Deal과 로그인한 sales
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        # when: text/plain 파일을 올린다
        response = await upload(http, ("notes.txt", b"plain text", "text/plain"))

    # then: 응답 mime이 text/plain이고 저장소에는 올린 바이트 파일 하나뿐이다
    assert response.json()["attachment"]["mime"] == "text/plain"
    assert use_cases.file_storage.file_count() == 1
    (stored,) = use_cases.file_storage._files.values()
    assert stored == b"plain text"


async def test_description_and_on_exists_are_optional() -> None:
    """설명과 on_exists를 생략해도 201이고 설명은 빈 문자열이다.

    테스트 코드: AT-002
    """
    # given: 저장 위치가 설정된 Deal과 로그인한 sales
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        # when: 설명·on_exists 없이 올린다
        response = await http.post(UPLOAD_URL, files=form(("a.pdf", b"x", "application/pdf")))

    # then: 201이고 설명이 ""다
    assert response.status_code == 201, response.text
    assert response.json()["attachment"]["description"] == ""


async def test_an_empty_file_is_accepted() -> None:
    """0바이트 파일도 201이다.

    테스트 코드: AT-005
    """
    # given: 저장 위치가 설정된 Deal과 로그인한 sales
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        # when: 0바이트 파일을 올린다
        response = await upload(http, ("empty.txt", b"", "text/plain"))

    # then: 201이고 크기가 0이다
    assert response.status_code == 201, response.text
    assert response.json()["attachment"]["size"] == 0


async def test_the_same_name_with_ask_is_409_file_exists() -> None:
    """같은 이름을 ask로 올리면 409 file-exists이다.

    테스트 코드: AT-017
    """
    # given: 저장 위치가 설정된 Deal과 "a.pdf"가 이미 올라가 있다
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        await upload(http)
        # when: 같은 이름을 ask로 올린다
        response = await upload(http, on_exists="ask")

    # then: 409 file-exists이고 문구에 파일 이름이 있으며 저장소 파일은 하나뿐이다
    body = problem(response, 409, "file-exists")
    assert body["title"] == "File Exists"
    assert body["detail"] == "같은 이름의 파일이 이미 있습니다: a.pdf"
    assert use_cases.file_storage.file_count() == 1


async def test_the_same_name_with_skip_is_200_skipped_without_an_attachment() -> None:
    """같은 이름을 skip으로 올리면 200 skipped이고 첨부·Location이 없다.

    테스트 코드: AT-018
    """
    # given: 저장 위치가 설정된 Deal과 "a.pdf"가 이미 올라가 있다
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        await upload(http)
        # when: 같은 이름을 skip으로 올린다
        response = await upload(http, on_exists="skip")

    # then: 200 skipped, attachment null이고 Location이 없다
    assert response.status_code == 200, response.text
    assert response.json() == {"outcome": "skipped", "attachment": None}
    assert "location" not in response.headers


async def test_the_same_name_with_replace_is_200_replaced_and_keeps_the_id() -> None:
    """같은 이름을 replace로 올리면 200 replaced이고 id가 같다.

    테스트 코드: AT-019
    """
    # given: 저장 위치가 설정된 Deal과 "a.pdf"가 이미 올라가 있다
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        first = (await upload(http)).json()["attachment"]
        # when: 더 긴 내용으로 replace 업로드한다
        response = await upload(
            http, ("a.pdf", b"newer content", "application/pdf"), on_exists="replace"
        )

    # then: 200 replaced이고 id가 같으며 크기가 새 내용이다
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "replaced"
    assert body["attachment"]["id"] == first["id"]
    assert body["attachment"]["size"] == 13


async def test_replace_by_another_sales_is_403_with_the_replace_sentence() -> None:
    """다른 sales가 replace하면 교체 권한 문구의 403이다.

    테스트 코드: AT-023
    """
    # given: kim이 "a.pdf"를 올려 두었다
    use_cases = await ready_use_cases()
    async with client_for(use_cases, login="kim") as kim:
        await upload(kim)
    async with client_for(use_cases, login="park") as park:
        # when: 다른 sales park이 replace로 올린다
        response = await upload(
            park, ("a.pdf", b"mine now", "application/pdf"), on_exists="replace"
        )

    # then: 403 forbidden "본인이 올린 파일만 교체할 수 있습니다."다
    assert problem(response, 403, "forbidden")["detail"] == "본인이 올린 파일만 교체할 수 있습니다."


async def test_an_admin_can_replace_anyones_file() -> None:
    """admin은 누구의 파일이든 교체할 수 있다.

    테스트 코드: AT-022
    """
    # given: kim이 "a.pdf"를 올려 두었다
    use_cases = await ready_use_cases()
    async with client_for(use_cases, login="kim") as kim:
        await upload(kim)
    async with client_for(use_cases, login="boss", role=Role.ADMIN) as boss:
        # when: admin이 replace로 올린다
        response = await upload(boss, ("a.pdf", b"admin", "application/pdf"), on_exists="replace")

    # then: 200이고 업로더가 admin으로 바뀐다
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
    """규칙 위반 업로드는 422 invalid-value와 문서의 문구다.

    테스트 코드: AT-006
    """
    # given: 저장 위치가 설정된 Deal과 로그인한 sales
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        # when: 규칙을 어긴 파일·설명으로 올린다
        response = await http.post(UPLOAD_URL, files=form(file, **fields))

    # then: 422 invalid-value이고 문구가 기대와 같으며 저장소에 파일이 없다
    assert problem(response, 422, "invalid-value")["detail"] == detail
    assert use_cases.file_storage.file_count() == 0


async def test_a_file_over_100mb_is_422_before_anything_is_stored() -> None:
    """100MB를 넘는 파일은 저장 전에 422이다.

    테스트 코드: AT-011
    """
    use_cases = await ready_use_cases()
    # given: 저장 위치가 설정된 Deal과 100MB+1바이트 파일
    too_big = ("big.bin", bytes(MAX_FILE_BYTES + 1), "application/octet-stream")
    async with client_for(use_cases) as http:
        # when: 그 파일을 올린다
        response = await upload(http, too_big)

    # then: 422 크기 초과 문구이고 저장소에 파일이 없다
    assert problem(response, 422, "invalid-value")["detail"] == FILE_TOO_LARGE
    assert use_cases.file_storage.file_count() == 0


async def test_an_unknown_on_exists_value_is_a_request_validation_error() -> None:
    """알 수 없는 on_exists 값은 422 request-validation이다.

    테스트 코드: AT-012
    """
    # given: 저장 위치가 설정된 Deal과 로그인한 sales
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        # when: on_exists "overwrite"로 올린다
        response = await upload(http, on_exists="overwrite")

    # then: 422 request-validation이고 저장소에 파일이 없다
    problem(response, 422, "request-validation")
    assert use_cases.file_storage.file_count() == 0


async def test_a_json_body_instead_of_multipart_is_a_validation_error_not_a_server_error() -> None:
    """multipart가 아닌 JSON 본문은 서버 오류가 아니라 검증 오류다.

    테스트 코드: AT-012
    """
    # given: 저장 위치가 설정된 Deal과 로그인한 sales
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        # when: JSON 본문으로 업로드 경로를 부른다
        response = await http.post(UPLOAD_URL, json={"description": "x"})

    # then: 415 또는 422이고 저장소에 파일이 없다
    assert response.status_code in {415, 422}, response.text
    assert use_cases.file_storage.file_count() == 0


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code"])
async def test_a_missing_or_malformed_deal_is_404_before_the_file_is_checked(code: str) -> None:
    """없는 Deal·형식이 틀린 code는 파일 검증보다 먼저 404이다.

    테스트 코드: AT-013
    """
    # given: 저장 위치가 설정된 Deal과 로그인한 sales
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        # when: 없는 Deal code에 파일 없이 올린다
        response = await http.post(f"/api/v1/deals/{code}/attachments", files=form(None))

    # then: 404 "Deal을 찾을 수 없습니다."다
    assert problem(response, 404, "not-found")["detail"] == "Deal을 찾을 수 없습니다."


async def test_a_read_only_user_is_403_even_for_a_missing_deal() -> None:
    """읽기 전용 user의 업로드는 없는 Deal이어도 403이다.

    테스트 코드: AT-016
    """
    # given: 저장 위치가 설정된 Deal과 로그인한 user
    use_cases = await ready_use_cases()
    async with client_for(use_cases, login="viewer", role=Role.USER) as http:
        # when: 있는 Deal과 없는 Deal에 올린다
        existing = await upload(http)
        missing = await http.post("/api/v1/deals/20991231-ZZZZ/attachments", files=form())

    # then: 둘 다 403 읽기 전용 문구이고 저장소에 파일이 없다
    for response in (existing, missing):
        assert problem(response, 403, "forbidden")["detail"] == READ_ONLY
    assert use_cases.file_storage.file_count() == 0


async def test_an_anonymous_request_is_401() -> None:
    """로그인하지 않은 업로드는 401이다.

    테스트 코드: AT-016
    """
    # given: 저장 위치가 설정된 Deal과 로그인하지 않은 요청
    use_cases = await ready_use_cases()
    async with client_for(use_cases, login=None) as http:
        # when: 업로드한다
        response = await upload(http)

    # then: 401 unauthenticated이고 저장소에 파일이 없다
    problem(response, 401, "unauthenticated")
    assert use_cases.file_storage.file_count() == 0


async def test_without_a_storage_location_the_upload_is_503_storage_unavailable() -> None:
    """저장 위치 설정이 없으면 업로드는 503 storage-unavailable이다.

    테스트 코드: AT-014
    """
    # given: 저장 위치 설정이 없는 Deal과 로그인한 sales
    use_cases = await ready_use_cases(storage=False)
    async with client_for(use_cases) as http:
        # when: 올바른 파일을 올린다
        response = await upload(http)

    # then: 503 storage-unavailable이고 업로드용 문구다
    body = problem(response, 503, "storage-unavailable")
    assert body["detail"] == UPLOAD_UNAVAILABLE
    assert body["title"] == "Storage Unavailable"


async def test_a_storage_location_that_cannot_be_written_is_503_storage_unavailable() -> None:
    """저장 위치에 쓸 수 없으면 업로드는 503 storage-unavailable이다.

    테스트 코드: AT-015
    """
    # given: 저장 위치에 쓸 수 없는 Deal
    use_cases = await ready_use_cases()
    use_cases.file_storage.block("/data")
    async with client_for(use_cases) as http:
        # when: 올바른 파일을 올린다
        response = await upload(http)

    # then: 503 storage-unavailable이고 업로드용 문구다
    assert problem(response, 503, "storage-unavailable")["detail"] == UPLOAD_UNAVAILABLE
