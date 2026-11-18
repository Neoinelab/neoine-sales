"""GET /api/v1/deals의 API 계약 문서: 앱이 만든 계약과 커밋된 openapi.json 모두."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
COMMITTED = Path(__file__).resolve().parents[3] / "openapi.json"
SORTS = {
    "name",
    "revenue_amount",
    "revenue_date",
    "last_updated_at",
    "status",
    "owner",
    "customer",
    "partner",
    "vendor",
    "forecast",
}


@pytest.fixture(scope="module", params=["app", "committed"])
def contract(request: pytest.FixtureRequest) -> dict[str, Any]:
    if request.param == "committed":
        loaded: dict[str, Any] = json.loads(COMMITTED.read_text(encoding="utf-8"))
        return loaded
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


@pytest.fixture
def parameters(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    listed = contract["paths"]["/api/v1/deals"]["get"]["parameters"]
    return {p["name"]: p for p in listed}


def _enum_values(schema: dict[str, Any], contract: dict[str, Any]) -> set[str]:
    """스키마의 enum 값. $ref(components)와 anyOf를 따라간다."""
    found: set[str] = set(schema.get("enum", []))
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        found |= _enum_values(contract["components"]["schemas"][name], contract)
    for option in schema.get("anyOf", []):
        found |= _enum_values(option, contract)
    return found


def test_the_bant_query_parameters_are_gone(parameters: dict[str, dict[str, Any]]) -> None:
    """Deal 목록 API에 bant_ 쿼리 파라미터가 더 이상 없다."""
    # when: 계약의 파라미터 이름을 모은다
    result = [name for name in parameters if name.startswith("bant_")]
    # then: bant_로 시작하는 이름이 없다 (전제: 앱 계약·커밋된 계약 모두)
    assert result == []


@pytest.mark.parametrize("name", ["overdue", "stale"])
def test_overdue_and_stale_are_optional_booleans_defaulting_to_false(
    parameters: dict[str, dict[str, Any]], name: str
) -> None:
    """overdue·stale은 기본값이 false인 선택 불리언 쿼리 파라미터다."""
    # when: 파라미터 정의를 꺼낸다
    parameter = parameters[name]

    # then: 쿼리 파라미터이고 필수가 아니며 boolean 타입에 기본값이 false다
    assert parameter["in"] == "query"
    assert parameter.get("required", False) is False
    assert parameter["schema"]["type"] == "boolean"
    assert parameter["schema"]["default"] is False


def test_sort_documents_the_ten_sortable_values(
    parameters: dict[str, dict[str, Any]], contract: dict[str, Any]
) -> None:
    """sort 파라미터는 정렬 가능한 열 열 가지를 문서화한다."""
    # when: sort 파라미터의 enum 값을 읽는다
    result = _enum_values(parameters["sort"]["schema"], contract)
    # then: 정렬 가능한 열 10개와 같다 (전제: 앱 계약·커밋된 계약 모두)
    assert result == SORTS


def test_forecast_key_is_an_array_parameter(parameters: dict[str, dict[str, Any]]) -> None:
    """forecast_key는 길이·개수 제한이 있는 반복 배열 쿼리 파라미터다."""
    # when: forecast_key 정의에서 배열 스키마를 고른다
    parameter = parameters["forecast_key"]
    options = parameter["schema"].get("anyOf", [parameter["schema"]])
    arrays = [o for o in options if o.get("type") == "array"]
    assert arrays, f"forecast_key must accept an array: {parameter['schema']}"
    array = arrays[0]

    # then: 쿼리 파라미터이고 필수가 아니며 문자열 50자·최대 100개 배열이고 반복(explode) 방식이다
    assert parameter["in"] == "query"
    assert parameter.get("required", False) is False
    assert array["items"]["type"] == "string"
    assert array["items"]["maxLength"] == 50
    assert array["maxItems"] == 100
    assert parameter.get("explode", True) is True


def test_the_period_parameters_and_the_sort_value_keep_their_names(
    parameters: dict[str, dict[str, Any]], contract: dict[str, Any]
) -> None:
    """응답 필드가 날짜(last_updated_on)로 바뀌어도 최종 업데이트 검색·정렬 요청 이름은 그대로다.

    테스트 코드: DL-030, DL-106
    """
    # when: 기간 파라미터와 sort 값을 읽는다 (전제: 앱 계약·커밋된 계약 모두)
    sort_values = _enum_values(parameters["sort"]["schema"], contract)
    # then: updated_from·updated_to와 정렬 값 last_updated_at이 그대로 있다
    assert {"updated_from", "updated_to"} <= set(parameters)
    assert "last_updated_at" in sort_values
    assert "last_updated_on" not in sort_values
    # then: 응답 스키마는 날짜 키를 쓰고 시각 키가 없다
    row = contract["components"]["schemas"]["DealRowResponse"]["properties"]
    assert {"last_updated_on", "status_changed_on"} <= set(row)
    assert not {"last_updated_at", "status_changed_at"} & set(row)


@pytest.mark.parametrize("name", ["DealRowResponse", "DealDetailResponse"])
def test_deal_responses_declare_a_required_non_negative_integer_unread_comment_count(
    contract: dict[str, Any], name: str
) -> None:
    """Deal 행·상세 응답에 required 정수 unread_comment_count(minimum 0, nullable 아님)가 있다.

    테스트 코드: CM-089
    """
    # when: 응답 스키마를 읽는다
    schema = contract["components"]["schemas"][name]
    prop = schema["properties"]["unread_comment_count"]

    # then: required이고 type integer, minimum 0이며 nullable이 아니다
    assert "unread_comment_count" in schema["required"]
    assert (prop["type"], prop["minimum"]) == ("integer", 0)
    assert "anyOf" not in prop


def test_the_list_query_parameters_do_not_include_unread_comment_count(
    parameters: dict[str, dict[str, Any]],
) -> None:
    """GET /deals 쿼리 파라미터에 unread_comment_count가 없다.

    테스트 코드: CM-089
    """
    # then: 읽지 않은 수로 거르거나 정렬하는 파라미터는 없다
    assert "unread_comment_count" not in parameters
