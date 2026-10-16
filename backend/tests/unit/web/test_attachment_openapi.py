"""첨부 API의 OpenAPI 계약(P2b AC-18, 7.1·7.2·7.3): 경로·메서드·multipart·응답 코드·스키마.

커밋된 openapi.json과의 일치(드리프트)는 functional/platform이 검사한다. 이 파일은 새 계약의
핵심을 직접 고정해, 스키마가 갱신되지 않았거나 필드가 빠진 경우를 구체적으로 드러낸다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

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
    paths = schema["paths"]

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
    assert expected <= _responses(schema, method, path)


def test_upload_takes_a_multipart_form_with_a_binary_file(schema: dict[str, Any]) -> None:
    body = schema["paths"][LIST]["post"]["requestBody"]["content"]

    assert set(body) == {"multipart/form-data"}
    form = _component(schema, str(body["multipart/form-data"]["schema"]["$ref"]).rsplit("/", 1)[-1])
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
    body = schema["paths"][LIST]["post"]["requestBody"]["content"]["multipart/form-data"]
    form = _component(schema, str(body["schema"]["$ref"]).rsplit("/", 1)[-1])
    on_exists = form["properties"]["on_exists"]
    resolved = (
        _component(schema, str(on_exists["$ref"]).rsplit("/", 1)[-1])
        if "$ref" in on_exists
        else on_exists
    )

    assert resolved["enum"] == ["ask", "replace", "skip"]
    assert resolved.get("default", on_exists.get("default")) == "ask"


def test_upload_success_responses_share_one_schema(schema: dict[str, Any]) -> None:
    responses = schema["paths"][LIST]["post"]["responses"]
    refs = {
        status: responses[status]["content"]["application/json"]["schema"]["$ref"]
        for status in ("200", "201")
    }

    assert refs["200"] == refs["201"]
    assert refs["200"].endswith("/AttachmentUploadResponse")


def test_download_is_a_binary_octet_stream(schema: dict[str, Any]) -> None:
    content = schema["paths"][DOWNLOAD]["get"]["responses"]["200"]["content"]

    assert set(content) == {"application/octet-stream"}
    assert content["application/octet-stream"]["schema"] == {"type": "string", "format": "binary"}


def test_delete_has_no_response_body(schema: dict[str, Any]) -> None:
    assert "content" not in schema["paths"][ONE]["delete"]["responses"]["204"]


def test_the_attachment_response_has_the_documented_required_fields(schema: dict[str, Any]) -> None:
    attachment = _component(schema, "AttachmentResponse")

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
    response = _component(schema, "AttachmentUploadResponse")
    props = response["properties"]

    assert props["outcome"]["enum"] == ["uploaded", "replaced", "skipped"]
    assert {o.get("type") for o in props["attachment"]["anyOf"]} == {None, "null"}
    assert set(response["required"]) == {"outcome", "attachment"}


def test_the_list_response_wraps_items(schema: dict[str, Any]) -> None:
    listing = _component(schema, "AttachmentList")

    assert set(listing["properties"]) == {"items"}
    assert listing["properties"]["items"]["type"] == "array"
