"""파트너 미팅 API의 OpenAPI 계약: 경로·메서드, 응답 코드, 요청·응답 필드, 태그."""

from typing import Any

import pytest

from app.domain.common.ids import MAX_ID
from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
BASE = "/api/v1/partner-meetings"
ID_ROUTE = f"{BASE}/{{meeting_id}}"
OPTIONS = f"{BASE}/deal-options"
ITEM_FIELDS = {"partner_company", "meeting_date", "content"}
RESPONSE_FIELDS = {
    "id",
    "partner_company",
    "meeting_date",
    "content",
    "author",
    "created_at",
    "updated_at",
}


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


def _resolve(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        node = schema["components"]["schemas"][node["$ref"].rsplit("/", 1)[1]]
    return node


def _body(schema: dict[str, Any], method: str, path: str) -> dict[str, Any]:
    body = schema["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"]
    return _resolve(schema, body)


def _response(schema: dict[str, Any], method: str, path: str, code: str) -> dict[str, Any]:
    content = schema["paths"][path][method]["responses"][code]["content"]["application/json"]
    return _resolve(schema, content["schema"])


def test_paths_and_methods(schema: dict[str, Any]) -> None:
    """미팅 경로는 목록·등록과 수정·삭제 두 개뿐이다.

    테스트 코드: PA-048
    """
    # when: 두 경로의 메서드를 읽는다
    paths = schema["paths"]
    # then: 컬렉션은 get·post, 개별 기록은 put·delete다
    assert set(paths[BASE]) == {"get", "post"}
    assert set(paths[ID_ROUTE]) == {"put", "delete"}


def test_every_operation_is_tagged_partner_meetings(schema: dict[str, Any]) -> None:
    """모든 작업의 태그는 partner-meetings다.

    테스트 코드: PA-048
    """
    # when·then: 두 경로의 모든 작업을 확인한다
    for path in (BASE, ID_ROUTE):
        for operation in schema["paths"][path].values():
            assert operation["tags"] == ["partner-meetings"], path


@pytest.mark.parametrize(
    ("method", "path", "success"),
    [
        ("get", BASE, "200"),
        ("post", BASE, "201"),
        ("put", ID_ROUTE, "200"),
        ("delete", ID_ROUTE, "204"),
    ],
)
def test_success_status_codes_and_401(
    schema: dict[str, Any], method: str, path: str, success: str
) -> None:
    """각 작업은 성공 코드와 401을 문서화한다.

    테스트 코드: PA-048
    """
    # when: 작업의 응답 코드를 읽는다
    responses = schema["paths"][path][method]["responses"]
    # then: 성공 코드와 401이 있다
    assert success in responses
    assert "401" in responses


@pytest.mark.parametrize(
    ("method", "path", "codes"),
    [
        ("get", BASE, {"422"}),
        ("post", BASE, {"403", "422"}),
        ("put", ID_ROUTE, {"403", "404", "422"}),
        ("delete", ID_ROUTE, {"403", "404", "422"}),
    ],
)
def test_error_status_codes_are_documented(
    schema: dict[str, Any], method: str, path: str, codes: set[str]
) -> None:
    """각 작업은 오류 코드를 문서화한다.

    테스트 코드: PA-048
    """
    # when: 작업의 응답 코드를 읽는다
    documented = set(schema["paths"][path][method]["responses"])
    # then: 기대한 오류 코드가 모두 있다
    assert codes <= documented


def test_reads_document_no_403(schema: dict[str, Any]) -> None:
    """목록 읽기는 403을 문서화하지 않는다(모든 역할이 읽는다).

    테스트 코드: PA-048
    """
    # when: 목록 읽기의 응답 코드를 읽는다
    responses = schema["paths"][BASE]["get"]["responses"]
    # then: 403이 없다
    assert "403" not in responses


def test_meeting_id_path_parameter_is_a_bounded_integer(schema: dict[str, Any]) -> None:
    """meeting_id 경로 값은 1 이상 MAX_ID 이하 정수다.

    테스트 코드: PA-048
    """
    # when·then: 수정·삭제의 meeting_id 파라미터 스키마를 확인한다
    for method in ("put", "delete"):
        (param,) = [
            p for p in schema["paths"][ID_ROUTE][method]["parameters"] if p["name"] == "meeting_id"
        ]
        assert param["schema"]["type"] == "integer"
        assert (param["schema"]["minimum"], param["schema"]["maximum"]) == (1, MAX_ID)


def test_list_query_parameters(schema: dict[str, Any]) -> None:
    """목록 쿼리 파라미터는 문서의 아홉 개이고 모두 선택이다.

    테스트 코드: PA-048
    """
    # when: 목록 파라미터를 읽는다
    params = {p["name"]: p for p in schema["paths"][BASE]["get"]["parameters"]}
    # then: 이름·limit 기본값·최대값·offset 최소값·선택 여부가 명세와 같다
    assert set(params) == {
        "partner",
        "content",
        "date_from",
        "date_to",
        "author_user_id",
        "sort",
        "order",
        "offset",
        "limit",
    }
    assert params["limit"]["schema"]["default"] == 10
    assert params["limit"]["schema"]["maximum"] == 200
    assert params["offset"]["schema"]["minimum"] == 0
    assert not any(p["required"] for p in params.values())


def _enum(schema: dict[str, Any], node: dict[str, Any]) -> set[str]:
    resolved = _resolve(schema, node)
    found = set(resolved.get("enum", []))
    for option in resolved.get("anyOf", []):
        found |= _enum(schema, option)
    return found


def test_the_sort_and_order_parameters_list_their_values(schema: dict[str, Any]) -> None:
    """sort와 order 파라미터는 허용 값을 나열한다.

    테스트 코드: PA-048
    """
    # when: sort·order 스키마를 읽는다
    params = {p["name"]: p["schema"] for p in schema["paths"][BASE]["get"]["parameters"]}
    # then: 네 정렬 키와 asc·desc다
    assert _enum(schema, params["sort"]) == {"meeting_date", "partner", "content", "author"}
    assert _enum(schema, params["order"]) == {"asc", "desc"}


def test_text_filters_document_their_max_lengths(schema: dict[str, Any]) -> None:
    """텍스트 조건은 최대 길이를 문서화한다.

    테스트 코드: PA-048
    """
    # given: 파라미터 스키마
    params = {p["name"]: p["schema"] for p in schema["paths"][BASE]["get"]["parameters"]}

    def max_length(node: dict[str, Any]) -> int:
        options = [node, *node.get("anyOf", [])]
        return int(next(o["maxLength"] for o in options if "maxLength" in o))

    # when·then: partner 200자, content 100자다
    assert max_length(params["partner"]) == 200
    assert max_length(params["content"]) == 100


def test_create_body_is_a_list_of_one_to_fifty_items(schema: dict[str, Any]) -> None:
    """등록 본문은 1~50개의 항목 목록이고 항목은 세 필드뿐이다.

    테스트 코드: PA-048
    """
    # when: 등록 본문 스키마를 읽는다
    body = _body(schema, "post", BASE)
    items = body["properties"]["items"]
    item = _resolve(schema, items["items"])
    # then: items 하나만 필수이고 1~50개이며 항목은 세 필수 필드, 추가 속성 금지다
    assert set(body["properties"]) == {"items"}
    assert body["required"] == ["items"]
    assert (items["minItems"], items["maxItems"]) == (1, 50)
    assert set(item["properties"]) == ITEM_FIELDS
    assert set(item["required"]) == ITEM_FIELDS
    assert item["additionalProperties"] is False


def test_update_body_is_one_item(schema: dict[str, Any]) -> None:
    """수정 본문은 항목 하나(세 필드, 추가 속성 금지)다.

    테스트 코드: PA-048
    """
    # when: 수정 본문 스키마를 읽는다
    body = _body(schema, "put", ID_ROUTE)
    # then: 세 필드뿐이고 추가 속성이 금지다
    assert set(body["properties"]) == ITEM_FIELDS
    assert body["additionalProperties"] is False


def test_item_field_lengths_are_documented(schema: dict[str, Any]) -> None:
    """항목 필드의 길이와 날짜 형식이 문서화된다.

    테스트 코드: PA-048
    """
    # when: 수정 본문의 속성을 읽는다
    properties = _body(schema, "put", ID_ROUTE)["properties"]
    # then: 회사명 200자, 날짜 형식 date다
    assert properties["partner_company"]["maxLength"] == 200
    assert properties["meeting_date"]["format"] == "date"


def test_list_response_is_a_counted_page_of_meetings(schema: dict[str, Any]) -> None:
    """목록 응답은 items·total·offset·limit의 쪽이다.

    테스트 코드: PA-048
    """
    # when: 목록 응답 스키마를 읽는다
    page = _response(schema, "get", BASE, "200")
    item = _resolve(schema, page["properties"]["items"]["items"])
    # then: 쪽 필드 넷과 기록 필드 일곱이다
    assert set(page["properties"]) == {"items", "total", "offset", "limit"}
    assert set(item["properties"]) == RESPONSE_FIELDS


def test_create_response_wraps_the_created_items(schema: dict[str, Any]) -> None:
    """등록 응답은 만든 기록들의 items 하나다.

    테스트 코드: PA-048
    """
    # when: 등록 응답 스키마를 읽는다
    body = _response(schema, "post", BASE, "201")
    item = _resolve(schema, body["properties"]["items"]["items"])
    # then: items만 있고 항목은 기록 필드 일곱이다
    assert set(body["properties"]) == {"items"}
    assert set(item["properties"]) == RESPONSE_FIELDS


def test_update_response_is_one_meeting(schema: dict[str, Any]) -> None:
    """수정 응답은 기록 하나다.

    테스트 코드: PA-048
    """
    # when: 수정 응답 스키마를 읽는다
    response = _response(schema, "put", ID_ROUTE, "200")
    # then: 기록 필드 일곱이다
    assert set(response["properties"]) == RESPONSE_FIELDS


def test_user_columns_use_the_shared_user_ref_schema(schema: dict[str, Any]) -> None:
    """작성자 열은 공용 UserRef 스키마를 쓴다.

    테스트 코드: PA-048
    """
    # when: 수정 응답의 author 속성을 읽는다
    item = _response(schema, "put", ID_ROUTE, "200")
    # then: UserRef를 가리킨다
    assert item["properties"]["author"]["$ref"].endswith("/UserRef")


def test_deal_options_path_is_not_in_openapi(schema: dict[str, Any]) -> None:
    """Deal 선택지 경로는 openapi에 없다.

    테스트 코드: PA-048
    """
    # when·then: deal-options 경로가 어디에도 없다
    assert OPTIONS not in schema["paths"]
    assert not any("deal-options" in path for path in schema["paths"])


def test_meeting_item_request_has_exactly_three_properties(schema: dict[str, Any]) -> None:
    """항목 요청은 정확히 세 속성이고 모두 필수다.

    테스트 코드: PA-048
    """
    # when: 수정 본문 스키마를 읽는다
    body = _body(schema, "put", ID_ROUTE)
    # then: 속성과 필수가 모두 세 필드다
    assert set(body["properties"]) == {"partner_company", "meeting_date", "content"}
    assert set(body["required"]) == {"partner_company", "meeting_date", "content"}


def test_sort_enum_has_no_deal(schema: dict[str, Any]) -> None:
    """정렬 값과 파라미터에 deal이 없다.

    테스트 코드: PA-048
    """
    # when: 목록 파라미터를 읽는다
    params = {p["name"]: p["schema"] for p in schema["paths"][BASE]["get"]["parameters"]}
    # then: sort 값에도 파라미터 이름에도 deal이 없다
    assert "deal" not in _enum(schema, params["sort"])
    assert "deal" not in set(params)


def test_deal_schemas_of_the_meeting_api_are_gone(schema: dict[str, Any]) -> None:
    """미팅 API의 Deal 관련 스키마가 없다.

    테스트 코드: PA-048
    """
    # when: 컴포넌트 스키마 이름을 읽는다
    names = set(schema["components"]["schemas"])
    # then: MeetingDeal·DealOption으로 시작하는 것이 없다
    assert not {n for n in names if n.startswith(("MeetingDeal", "DealOption"))}


def test_the_deletion_impact_response_has_four_counts(schema: dict[str, Any]) -> None:
    """Deal 삭제 영향 응답은 네 건수 키뿐이다(미팅 건수 없음).

    테스트 코드: PA-044, PA-048
    """
    # when: 삭제 영향 응답 스키마를 읽는다
    impact = _response(schema, "get", "/api/v1/deals/{code}/deletion-impact", "200")
    # then: 속성과 필수가 모두 네 건수다
    counts = {"history_count", "action_count", "attachment_count", "license_contract_count"}
    assert set(impact["properties"]) == counts
    assert set(impact["required"]) == counts
