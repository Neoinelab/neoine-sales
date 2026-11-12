"""첨부 API의 OpenAPI 계약(7.1·7.2·7.3): 경로·메서드·multipart·응답 코드·스키마.

커밋된 openapi.json과의 일치(드리프트)는 platform 단위 테스트가 검사한다. 이 파일은 새 계약의
핵심을 직접 고정해, 스키마가 갱신되지 않았거나 필드가 빠진 경우를 구체적으로 드러낸다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
LIST = "/api/v1/deals/{code}/attachments"
ONE = "/api/v1/attachments/{attachment_id}"
DOWNLOAD = "/api/v1/attachments/{attachment_id}/download"


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


def _responses(schema: dict[str, Any], method: str, path: str) -> set[str]:
    return set(schema["paths"][path][method]["responses"])


def _component(schema: dict[str, Any], name: str) -> dict[str, Any]:
    return dict(schema["components"]["schemas"][name])


def test_attachment_paths_and_methods(schema: dict[str, Any]) -> None:
    """첨부 경로와 메서드가 계약대로다."""
    # given: 앱의 OpenAPI 스키마
    paths = schema["paths"]

    # when·then: 목록은 get·post, 단건은 get·delete, 다운로드는 get이다
    assert set(paths[LIST]) == {"get", "post"}
    assert set(paths[ONE]) == {"get", "delete"}
    assert set(paths[DOWNLOAD]) == {"get"}


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("get", LIST, {"200", "404"}),
        ("post", LIST, {"200", "201", "403", "404", "409", "422", "503"}),
        ("get", ONE, {"200", "404"}),
        ("get", DOWNLOAD, {"200", "404", "503"}),
        ("delete", ONE, {"204", "403", "404"}),
    ],
)
def test_documented_success_and_problem_responses(
    schema: dict[str, Any], method: str, path: str, expected: set[str]
) -> None:
    """각 경로는 문서의 성공·오류 응답 코드를 갖는다."""
    # when·then: 문서의 응답 코드가 모두 선언되어 있다 (전제: 앱의 OpenAPI 스키마)
    assert expected <= _responses(schema, method, path)


def test_upload_takes_a_multipart_form_with_a_binary_file(schema: dict[str, Any]) -> None:
    """업로드는 이진 파일 파트가 있는 multipart 폼을 받는다."""
    # given: 업로드 요청 본문 정의
    body = schema["paths"][LIST]["post"]["requestBody"]["content"]

    assert set(body) == {"multipart/form-data"}
    # when: 폼 스키마를 읽는다
    form = _component(schema, str(body["multipart/form-data"]["schema"]["$ref"]).rsplit("/", 1)[-1])
    # then: 파트는 file·description·on_exists이고 file은 이진 문자열이며 모두 필수가 아니다
    props = form["properties"]
    assert set(props) == {"file", "description", "on_exists"}
    file_schema = props["file"]
    options = file_schema.get("anyOf", [file_schema])
    # 파일 파트: 이진 문자열(OpenAPI 3.1은 contentMediaType, 3.0 표기는 format=binary)
    assert any(
        o.get("type") == "string" and (o.get("format") == "binary" or "contentMediaType" in o)
        for o in options
    )
    assert "file" not in form.get("required", [])
    assert "description" not in form.get("required", [])
    assert "on_exists" not in form.get("required", [])


def test_on_exists_is_the_closed_set_ask_replace_skip(schema: dict[str, Any]) -> None:
    """on_exists는 ask·replace·skip 닫힌 집합이고 기본값은 ask다."""
    # given: 업로드 요청 폼 스키마
    body = schema["paths"][LIST]["post"]["requestBody"]["content"]["multipart/form-data"]
    form = _component(schema, str(body["schema"]["$ref"]).rsplit("/", 1)[-1])
    # when: on_exists 정의를 읽는다
    on_exists = form["properties"]["on_exists"]
    resolved = (
        _component(schema, str(on_exists["$ref"]).rsplit("/", 1)[-1])
        if "$ref" in on_exists
        else on_exists
    )

    # then: 허용 값이 세 개이고 기본값이 ask다
    assert resolved["enum"] == ["ask", "replace", "skip"]
    assert resolved.get("default", on_exists.get("default")) == "ask"


def test_upload_success_responses_share_one_schema(schema: dict[str, Any]) -> None:
    """업로드의 200·201 응답은 같은 스키마를 쓴다."""
    # given: 업로드 응답 정의
    responses = schema["paths"][LIST]["post"]["responses"]
    # when: 200과 201의 스키마 참조를 읽는다
    refs = {
        status: responses[status]["content"]["application/json"]["schema"]["$ref"]
        for status in ("200", "201")
    }

    # then: 둘이 같은 AttachmentUploadResponse다
    assert refs["200"] == refs["201"]
    assert refs["200"].endswith("/AttachmentUploadResponse")


def test_download_is_a_binary_octet_stream(schema: dict[str, Any]) -> None:
    """다운로드 응답은 이진 octet-stream이다."""
    # when: 다운로드 200 응답 정의를 읽는다
    content = schema["paths"][DOWNLOAD]["get"]["responses"]["200"]["content"]

    # then: 콘텐츠 타입이 octet-stream 하나이고 스키마가 binary 문자열이다
    assert set(content) == {"application/octet-stream"}
    assert content["application/octet-stream"]["schema"] == {"type": "string", "format": "binary"}


def test_delete_has_no_response_body(schema: dict[str, Any]) -> None:
    """삭제 204 응답에는 본문이 없다."""
    # when·then: 204 응답에 content가 없다 (전제: 앱의 OpenAPI 스키마)
    assert "content" not in schema["paths"][ONE]["delete"]["responses"]["204"]


def test_the_attachment_response_has_the_documented_required_fields(schema: dict[str, Any]) -> None:
    """첨부 응답은 문서의 여덟 필드를 모두 필수로 가진다."""
    # when: AttachmentResponse 스키마를 읽는다
    attachment = _component(schema, "AttachmentResponse")

    # then: 필드가 정확히 여덟이고 모두 필수이며 업로더는 UserRef다
    assert set(attachment["properties"]) == {
        "id",
        "deal_code",
        "file_name",
        "description",
        "size",
        "mime",
        "uploaded_by",
        "uploaded_at",
    }
    assert set(attachment["required"]) == set(attachment["properties"])
    assert attachment["properties"]["uploaded_by"]["$ref"].endswith("/UserRef")


def test_the_upload_response_outcome_is_a_closed_set_and_the_attachment_is_nullable(
    schema: dict[str, Any],
) -> None:
    """업로드 응답의 outcome은 닫힌 집합이고 attachment는 null일 수 있다."""
    # when: AttachmentUploadResponse 스키마를 읽는다
    response = _component(schema, "AttachmentUploadResponse")
    props = response["properties"]

    # then: outcome은 세 값이고 attachment는 nullable이며 둘 다 필수다
    assert props["outcome"]["enum"] == ["uploaded", "replaced", "skipped"]
    assert {o.get("type") for o in props["attachment"]["anyOf"]} == {None, "null"}
    assert set(response["required"]) == {"outcome", "attachment"}


def test_the_list_response_wraps_items(schema: dict[str, Any]) -> None:
    """목록 응답은 items 배열을 감싼다."""
    # when: AttachmentList 스키마를 읽는다
    listing = _component(schema, "AttachmentList")

    # then: 필드는 items뿐이고 배열이다
    assert set(listing["properties"]) == {"items"}
    assert listing["properties"]["items"]["type"] == "array"
