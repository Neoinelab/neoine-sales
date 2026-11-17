"""Deal Comment API의 OpenAPI 계약: 경로 6개(PUT 없음), 응답 키·action·read_at, 읽음 처리·읽지 않은
수, Action 요청·응답의 memo 제거와 comment, History 구분 comment, 삭제 영향 comment_count.

커밋된 openapi.json과의 일치(드리프트)는 PL-034(`test_openapi_contract.py`)가 검사한다. 이
파일은 새 계약의 핵심을 직접 고정한다.
"""

from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
LIST_PATH = "/api/v1/deals/{code}/comments"
SINGLE_PATH = "/api/v1/deal-comments/{comment_id}"
READS_PATH = "/api/v1/deals/{code}/comment-reads"
COUNTS_PATH = "/api/v1/deals/{code}/comment-counts"
RESPONSE_KEYS = {
    "id",
    "deal_code",
    "action_id",
    "action",
    "body",
    "author",
    "created_at",
    "updated_at",
    "read_at",
}


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


def _is_nullable(prop: dict[str, Any]) -> bool:
    return any(option.get("type") == "null" for option in prop.get("anyOf", []))


def _request_schema(schema: dict[str, Any], method: str, path: str) -> dict[str, Any]:
    body = schema["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"]
    name = str(body["$ref"]).rsplit("/", 1)[-1]
    found: dict[str, Any] = schema["components"]["schemas"][name]
    return found


def test_the_six_comment_paths_exist_without_put_and_document_their_errors(
    schema: dict[str, Any],
) -> None:
    """Comment 경로 6개가 있고 PUT은 없으며 쓰기는 403·404·422를, 조회는 404·422를 문서화한다.

    테스트 코드: CM-046, CM-057
    """
    # when: 경로와 operation을 읽는다
    paths = schema["paths"]

    # then: 한 건 경로에는 get·delete뿐이고 수정(put)이 없다
    assert set(paths[LIST_PATH]) == {"get", "post"}
    assert set(paths[SINGLE_PATH]) == {"get", "delete"}
    assert set(paths[READS_PATH]) == {"post"}
    assert set(paths[COUNTS_PATH]) == {"get"}
    # then: 쓰기 경로는 401·403·404·422를, 조회 경로는 401·404·422를 문서화한다
    for method, path in (
        ("post", LIST_PATH),
        ("delete", SINGLE_PATH),
        ("post", READS_PATH),
    ):
        assert {"401", "403", "404", "422"} <= set(paths[path][method]["responses"]), (method, path)
    for method, path in (("get", LIST_PATH), ("get", SINGLE_PATH)):
        assert {"401", "404", "422"} <= set(paths[path][method]["responses"]), (method, path)
    assert {"401", "404"} <= set(paths[COUNTS_PATH]["get"]["responses"])
    # then: 작성은 201, 삭제·읽음 처리는 204이고 태그는 deal-comments다
    assert "201" in paths[LIST_PATH]["post"]["responses"]
    assert "204" in paths[SINGLE_PATH]["delete"]["responses"]
    assert "204" in paths[READS_PATH]["post"]["responses"]
    for path, method in ((LIST_PATH, "post"), (READS_PATH, "post"), (COUNTS_PATH, "get")):
        assert paths[path][method]["tags"] == ["deal-comments"]


def test_the_response_has_the_nine_keys_with_nullable_action_id_action_and_read_at(
    schema: dict[str, Any],
) -> None:
    """DealCommentResponse의 required는 아홉 키, action_id·action·read_at은 nullable,
    deal_code는 아님, body에 maxLength가 없다. action은 {id, acted_on, action, next_action}이다.

    테스트 코드: CM-046, CM-059
    """
    # when: 응답 스키마를 읽는다
    schemas = schema["components"]["schemas"]
    response = schemas["DealCommentResponse"]
    props = response["properties"]

    # then: required와 속성이 CM-R9의 아홉 키다
    assert set(response["required"]) == RESPONSE_KEYS
    assert set(props) == RESPONSE_KEYS
    # then: action_id·action·read_at만 null을 허용하고 deal_code는 아니며 body에 maxLength가 없다
    for name in ("action_id", "action", "read_at"):
        assert _is_nullable(props[name]), name
    assert not _is_nullable(props["deal_code"])
    assert "maxLength" not in props["body"]
    # then: read_at은 date-time이다
    assert any(o.get("format") == "date-time" for o in props["read_at"]["anyOf"])
    # then: action 요약 스키마는 네 키다
    ref = next(o["$ref"] for o in props["action"]["anyOf"] if "$ref" in o)
    summary = schemas[str(ref).rsplit("/", 1)[-1]]
    assert set(summary["properties"]) == {"id", "acted_on", "action", "next_action"}
    assert set(summary["required"]) == {"id", "acted_on", "action", "next_action"}
    assert summary["properties"]["acted_on"]["format"] == "date"
    # then: 목록 응답은 items 하나뿐이다
    listing = schemas["DealCommentList"]
    assert set(listing["properties"]) == {"items"}


def test_the_comment_requests_take_only_the_documented_keys_and_no_update_schema_exists(
    schema: dict[str, Any],
) -> None:
    """작성 요청은 body(필수)·action_id(선택), 읽음 처리 요청은 comment_ids(1~500 정수 배열)뿐이고
    수정 요청 스키마는 없다.

    테스트 코드: CM-046, CM-059
    """
    # when: 작성·읽음 처리 요청 스키마를 읽는다
    create = _request_schema(schema, "post", LIST_PATH)
    reads = _request_schema(schema, "post", READS_PATH)

    # then: 작성은 body 필수·action_id 선택(nullable)이다
    assert set(create["properties"]) == {"body", "action_id"}
    assert create["required"] == ["body"]
    assert _is_nullable(create["properties"]["action_id"])
    assert "maxLength" not in create["properties"]["body"]
    assert create["additionalProperties"] is False
    # then: 읽음 처리는 comment_ids(정수 배열, 1~500개)가 필수이고 모르는 키는 거절한다
    ids = reads["properties"]["comment_ids"]
    assert reads["required"] == ["comment_ids"]
    assert reads["additionalProperties"] is False
    assert ids["type"] == "array"
    assert ids["items"]["type"] == "integer"
    assert (ids["minItems"], ids["maxItems"]) == (1, 500)
    # then: 수정 요청 스키마는 없다
    assert "DealCommentUpdateRequest" not in schema["components"]["schemas"]


def test_the_counts_response_has_unread_and_by_action(schema: dict[str, Any]) -> None:
    """읽지 않은 수 응답은 unread(정수)와 by_action({action_id, unread} 배열)이 필수다.

    테스트 코드: CM-059
    """
    # when: 응답 스키마를 읽는다
    schemas = schema["components"]["schemas"]
    ok = schema["paths"][COUNTS_PATH]["get"]["responses"]["200"]["content"]["application/json"]
    counts = schemas[str(ok["schema"]["$ref"]).rsplit("/", 1)[-1]]

    # then: unread는 정수, by_action은 배열이고 둘 다 필수다
    assert set(counts["properties"]) == {"unread", "by_action"}
    assert set(counts["required"]) == {"unread", "by_action"}
    assert counts["properties"]["unread"]["type"] == "integer"
    assert counts["properties"]["by_action"]["type"] == "array"
    item = schemas[str(counts["properties"]["by_action"]["items"]["$ref"]).rsplit("/", 1)[-1]]
    assert set(item["properties"]) == {"action_id", "unread"}
    assert set(item["required"]) == {"action_id", "unread"}


def test_the_action_requests_and_response_drop_memo_and_the_create_request_gets_comment(
    schema: dict[str, Any],
) -> None:
    """DealActionResponse·DealActionUpdateRequest에 memo가 없고, DealActionCreateRequest·
    NextActionStatusRequest에 memo가 없으며 comment(문자열, required 아님)가 있다.

    테스트 코드: CM-046
    """
    # when: 관련 스키마를 읽는다
    schemas = schema["components"]["schemas"]
    create = schemas["DealActionCreateRequest"]
    status = schemas["NextActionStatusRequest"]

    # then: 응답·수정 요청에는 memo도 comment도 없다
    for name in ("DealActionResponse", "DealActionUpdateRequest"):
        assert "memo" not in schemas[name]["properties"], name
        assert "comment" not in schemas[name]["properties"], name
    assert "memo" not in schemas["DealActionResponse"]["required"]
    # then: 등록·상태 변경 요청에는 memo가 없고 comment가 문자열 선택 필드다(길이 상한 없음)
    for request in (create, status):
        assert "memo" not in request["properties"]
        assert request["properties"]["comment"]["type"] == "string"
        assert "maxLength" not in request["properties"]["comment"]
        assert "comment" not in request["required"]


def test_history_category_has_comment_and_the_deletion_impact_has_comment_count(
    schema: dict[str, Any],
) -> None:
    """History 구분 enum에 comment가 있고 삭제 영향 응답에 comment_count(정수, required)가 있다.

    테스트 코드: CM-046, DD-040
    """
    # when: 관련 스키마를 읽는다
    category = schema["components"]["schemas"]["HistoryCategory"]
    impact = schema["components"]["schemas"]["DeletionImpactResponse"]

    # then: 구분은 13값이고 comment가 있다
    assert "comment" in category["enum"]
    assert len(category["enum"]) == 13
    # then: comment_count가 정수 필수 필드다
    assert impact["properties"]["comment_count"]["type"] == "integer"
    assert "comment_count" in impact["required"]
