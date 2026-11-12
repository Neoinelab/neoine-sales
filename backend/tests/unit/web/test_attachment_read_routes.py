"""첨부 조회·다운로드·삭제 라우터(7.1): 목록, 단건, 다운로드 헤더, 삭제 판정 순서.

FakeUseCases·FakeFileStorage 위에서 HTTP 계약을 확인한다.
실제 DB·디스크는 infra 단위 테스트가 맡는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.storage.errors import DOWNLOAD_UNAVAILABLE
from app.domain.auth.principal import Role
from tests.support.ids import MISSING_ID
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


async def _uploaded_id(
    use_cases: FakeUseCases,
    name: str = "a.pdf",
    data: bytes = b"hello",
    mime: str = "application/pdf",
    login: str = "kim",
) -> int:
    async with client_for(use_cases, login=login) as http:
        response = await upload(http, (name, data, mime))
    return int(response.json()["attachment"]["id"])


async def test_the_list_is_newest_first_and_open_to_every_role() -> None:
    """목록은 모든 역할이 읽을 수 있고 최신 업로드 순이다.

    테스트 코드: AT-026
    """
    # given: 두 파일이 차례로 올라간 Deal
    use_cases = await ready_use_cases()
    first = await _uploaded_id(use_cases, "first.pdf")
    second = await _uploaded_id(use_cases, "second.pdf")

    for role in (Role.ADMIN, Role.SALES, Role.USER):
        async with client_for(use_cases, login=f"{role.value}-reader", role=role) as http:
            # when: admin·sales·user가 각각 목록을 읽는다
            response = await http.get(UPLOAD_URL)

        # then: 200이고 최신 파일이 먼저이며 항목 키가 문서와 같다
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == {"items"}
        assert [item["id"] for item in body["items"]] == [second, first]
        assert set(body["items"][0]) == ATTACHMENT_KEYS


async def test_the_list_of_a_deal_without_files_is_empty() -> None:
    """첨부가 없는 Deal의 목록은 빈 items이다.

    테스트 코드: AT-027
    """
    # given: 첨부가 없는 Deal
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        # when: 목록을 읽는다
        response = await http.get(UPLOAD_URL)

    # then: `{"items": []}`다
    assert response.json() == {"items": []}


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code"])
async def test_the_list_of_a_missing_or_malformed_deal_is_404(code: str) -> None:
    """없는 Deal·형식이 틀린 code의 목록은 404이다.

    테스트 코드: AT-028
    """
    # given: 저장 위치가 설정된 Deal
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        # when: 없는 Deal code의 목록을 읽는다
        response = await http.get(f"/api/v1/deals/{code}/attachments")

    # then: 404 "Deal을 찾을 수 없습니다."다
    assert problem(response, 404, "not-found")["detail"] == "Deal을 찾을 수 없습니다."


async def test_the_list_needs_a_login() -> None:
    """로그인하지 않으면 목록은 401이다.

    테스트 코드: AT-028
    """
    # given: 로그인하지 않은 요청
    use_cases = await ready_use_cases()
    async with client_for(use_cases, login=None) as http:
        # when: 목록을 읽는다
        response = await http.get(UPLOAD_URL)

    # then: 401 unauthenticated다
    problem(response, 401, "unauthenticated")


async def test_attachment_ids_are_json_integers() -> None:
    """첨부 id와 업로더 id는 JSON 정수다.

    테스트 코드: AT-026
    """
    use_cases = await ready_use_cases()
    # given: 파일이 올라간 Deal
    attachment_id = await _uploaded_id(use_cases)
    async with client_for(use_cases) as http:
        # when: 단건과 목록을 읽는다
        single = (await http.get(f"/api/v1/attachments/{attachment_id}")).json()
        listed = (await http.get(UPLOAD_URL)).json()

    # then: 첨부 id와 업로더 id가 정수 타입이다
    for body in (single, listed["items"][0]):
        assert type(body["id"]) is int
        assert type(body["uploaded_by"]["id"]) is int


async def test_one_attachment_is_readable_by_a_read_only_user() -> None:
    """user도 id로 첨부 한 건을 읽는다.

    테스트 코드: AT-029
    """
    use_cases = await ready_use_cases()
    # given: 5바이트 "a.pdf"가 올라가 있다
    attachment_id = await _uploaded_id(use_cases, "a.pdf", b"12345")
    async with client_for(use_cases, login="viewer", role=Role.USER) as http:
        # when: user가 단건을 읽는다
        response = await http.get(f"/api/v1/attachments/{attachment_id}")

    # then: 200이고 키가 문서와 같으며 id·이름·크기·Deal이 맞다
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
    """없는 id의 단건·다운로드는 404 문구이다.

    테스트 코드: AT-029
    """
    # given: 저장 위치가 설정된 Deal
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        # when: 없는 id로 단건과 다운로드를 요청한다
        single = await http.get(f"/api/v1/attachments/{MISSING_ID}")
        download = await http.get(f"/api/v1/attachments/{MISSING_ID}/download")

    # then: 둘 다 404 "첨부 파일을 찾을 수 없습니다."다
    for response in (single, download):
        assert problem(response, 404, "not-found")["detail"] == NOT_FOUND


async def test_download_streams_the_bytes_as_an_octet_stream_attachment() -> None:
    """다운로드는 저장 바이트를 octet-stream 첨부로 내려준다.

    테스트 코드: AT-030
    """
    use_cases = await ready_use_cases()
    # given: 바이너리 "report.pdf"가 올라가 있다
    data = b"\x00\x01binary\xff" * 1000
    attachment_id = await _uploaded_id(use_cases, "report.pdf", data)
    async with client_for(use_cases, login="viewer", role=Role.USER) as http:
        # when: user가 내려받는다
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    # then: 200이고 본문이 같으며 Content-Type·Content-Length·Content-Disposition이 기대대로다
    assert response.status_code == 200, response.text
    assert response.content == data
    assert response.headers["content-type"].split(";")[0] == "application/octet-stream"
    assert response.headers["content-length"] == str(len(data))
    assert response.headers["content-disposition"] == (
        "attachment; filename=\"report.pdf\"; filename*=UTF-8''report.pdf"
    )


async def test_download_never_serves_the_clients_content_type() -> None:
    """클라이언트가 올린 Content-Type과 무관하게 octet-stream 첨부로 내려준다.

    테스트 코드: AT-030
    """
    use_cases = await ready_use_cases()
    # given: text/html로 올린 "page.html"
    attachment_id = await _uploaded_id(
        use_cases, "page.html", b"<script>alert(1)</script>", "text/html"
    )
    async with client_for(use_cases) as http:
        # when: 내려받는다
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    # then: octet-stream이고 Content-Disposition이 attachment다
    assert response.headers["content-type"].split(";")[0] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment;")


async def test_download_keeps_a_korean_file_name_in_the_utf8_parameter() -> None:
    """한글 파일 이름은 UTF-8 파라미터에 보존된다.

    테스트 코드: AT-031
    """
    use_cases = await ready_use_cases()
    # given: 한글 이름 파일이 올라가 있다
    attachment_id = await _uploaded_id(use_cases, "견적서.pdf")
    async with client_for(use_cases) as http:
        # when: 내려받는다
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    # then: 대체 이름은 `_`, filename*는 퍼센트 인코딩이다
    assert response.headers["content-disposition"] == (
        "attachment; filename=\"___.pdf\"; filename*=UTF-8''%EA%B2%AC%EC%A0%81%EC%84%9C.pdf"
    )


async def test_download_of_an_empty_file_has_zero_length() -> None:
    """0바이트 파일은 빈 본문과 길이 0으로 내려간다.

    테스트 코드: AT-032
    """
    use_cases = await ready_use_cases()
    # given: 0바이트 파일이 올라가 있다
    attachment_id = await _uploaded_id(use_cases, "empty.txt", b"")
    async with client_for(use_cases) as http:
        # when: 내려받는다
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    # then: 200이고 본문이 비어 있으며 Content-Length가 0이다
    assert (response.status_code, response.content) == (200, b"")
    assert response.headers["content-length"] == "0"


async def test_download_of_a_row_whose_file_is_gone_is_404_with_the_content_sentence() -> None:
    """디스크 파일이 없으면 404 내용 없음 문구이다.

    테스트 코드: AT-034
    """
    use_cases = await ready_use_cases()
    # given: 파일이 올라간 뒤 디스크 파일이 사라졌다
    attachment_id = await _uploaded_id(use_cases)
    use_cases.file_storage._files.clear()
    async with client_for(use_cases) as http:
        # when: 내려받는다
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    # then: 404 "첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요."다
    assert problem(response, 404, "not-found")["detail"] == CONTENT_MISSING


async def test_download_without_a_storage_location_is_503() -> None:
    """저장 위치 설정이 없으면 다운로드는 503이다.

    테스트 코드: AT-035
    """
    use_cases = await ready_use_cases()
    # given: 파일이 올라간 뒤 저장 위치 설정을 지웠다
    attachment_id = await _uploaded_id(use_cases)
    use_cases.uow.storage_settings._items.clear()
    async with client_for(use_cases) as http:
        # when: 내려받는다
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    # then: 503 storage-unavailable 다운로드 문구다
    assert problem(response, 503, "storage-unavailable")["detail"] == DOWNLOAD_UNAVAILABLE


async def test_download_of_a_file_that_cannot_be_read_is_503_not_404() -> None:
    """읽을 수 없는 파일의 다운로드는 404가 아니라 503이다.

    테스트 코드: AT-035
    """
    use_cases = await ready_use_cases()
    # given: 파일이 올라간 뒤 읽기가 실패하게 했다
    attachment_id = await _uploaded_id(use_cases)
    use_cases.file_storage.fail_reads = True
    async with client_for(use_cases) as http:
        # when: 내려받는다
        response = await http.get(f"/api/v1/attachments/{attachment_id}/download")

    # then: 503 storage-unavailable 다운로드 문구다
    assert problem(response, 503, "storage-unavailable")["detail"] == DOWNLOAD_UNAVAILABLE


async def test_the_uploader_deletes_the_file_with_204() -> None:
    """업로더가 지우면 204이고 이후 조회는 404, 디스크 파일도 없다.

    테스트 코드: AT-036
    """
    # given: 업로더가 올린 파일
    use_cases = await ready_use_cases()
    attachment_id = await _uploaded_id(use_cases)
    async with client_for(use_cases) as http:
        # when: 업로더가 지운다
        response = await http.delete(f"/api/v1/attachments/{attachment_id}")
        # when: 같은 id를 다시 읽는다
        again = await http.get(f"/api/v1/attachments/{attachment_id}")

    # then: 204 빈 본문이고 다시 읽으면 404이며 저장소에 파일이 없다
    assert (response.status_code, response.content) == (204, b"")
    problem(again, 404, "not-found")
    assert use_cases.file_storage.file_count() == 0


async def test_another_sales_is_403_and_an_admin_is_204() -> None:
    """다른 sales의 삭제는 403, admin의 삭제는 204이다.

    테스트 코드: AT-037
    """
    # given: kim이 올린 파일
    use_cases = await ready_use_cases()
    attachment_id = await _uploaded_id(use_cases)
    async with client_for(use_cases, login="park") as park:
        # when: 다른 sales park이 지운다
        denied = await park.delete(f"/api/v1/attachments/{attachment_id}")
    async with client_for(use_cases, login="boss", role=Role.ADMIN) as boss:
        # when: admin이 지운다
        allowed = await boss.delete(f"/api/v1/attachments/{attachment_id}")

    # then: park은 삭제 권한 문구의 403이고 admin은 204다
    assert problem(denied, 403, "forbidden")["detail"] == "본인이 올린 파일만 삭제할 수 있습니다."
    assert allowed.status_code == 204


async def test_a_read_only_user_is_403_before_the_file_is_looked_up() -> None:
    """user의 삭제는 없는 id여도 403이다.

    테스트 코드: AT-038
    """
    use_cases = await ready_use_cases()
    # given: 파일이 올라가 있고 user로 로그인했다
    attachment_id = await _uploaded_id(use_cases)
    async with client_for(use_cases, login="viewer", role=Role.USER) as http:
        # when: 있는 id와 없는 id를 지운다
        existing = await http.delete(f"/api/v1/attachments/{attachment_id}")
        missing = await http.delete(f"/api/v1/attachments/{MISSING_ID}")

    # then: 둘 다 403 읽기 전용 문구이고 파일은 그대로다
    for response in (existing, missing):
        assert problem(response, 403, "forbidden")["detail"] == READ_ONLY
    assert use_cases.file_storage.file_count() == 1


async def test_deleting_an_unknown_attachment_is_404() -> None:
    """sales의 없는 id 삭제는 404이다.

    테스트 코드: AT-038
    """
    # given: 저장 위치가 설정된 Deal과 로그인한 sales
    use_cases = await ready_use_cases()
    async with client_for(use_cases) as http:
        # when: 없는 id를 지운다
        response = await http.delete(f"/api/v1/attachments/{MISSING_ID}")

    # then: 404 "첨부 파일을 찾을 수 없습니다."다
    assert problem(response, 404, "not-found")["detail"] == NOT_FOUND


async def test_deleting_needs_a_login() -> None:
    """로그인하지 않은 삭제는 401이다.

    테스트 코드: AT-038
    """
    use_cases = await ready_use_cases()
    # given: 파일이 올라가 있고 로그인하지 않은 요청이다
    attachment_id = await _uploaded_id(use_cases)
    async with client_for(use_cases, login=None) as anonymous:
        # when: 지운다
        response = await anonymous.delete(f"/api/v1/attachments/{attachment_id}")

    # then: 401 unauthenticated다
    problem(response, 401, "unauthenticated")
