"""Action 생성 요청의 선택 필드 close_previous_next_action_id.

수정 요청에는 없다. 기본값은 null이라 기존 클라이언트는 영향이 없다.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from app.application.deal_action.inputs import DealActionInput
from app.domain.deal_action.value_objects import DealActionId
from app.main import create_app
from app.web.schemas.deal_action import DealActionCreateRequest, DealActionUpdateRequest
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
BODY: dict[str, Any] = {
    "action_type": {"name": "미팅"},
    "action": "킥오프 미팅",
    "next_action": "요구사항 문서 전달",
    "due_date": "2026-03-10",
}
FIELD = "close_previous_next_action_id"


def _create(**extra: object) -> DealActionCreateRequest:
    return DealActionCreateRequest(**{**BODY, **extra})


def test_close_previous_id_maps_to_input() -> None:
    """이전 Next Action id가 입력으로 넘어간다.

    테스트 코드: AC-036
    """
    # when: id를 실은 등록 요청을 입력으로 바꾼다
    data = _create(close_previous_next_action_id=7).to_input()

    # then: 입력에 그 id가 담긴다
    assert isinstance(data, DealActionInput)
    assert data.close_previous_next_action_id == DealActionId(7)


def test_close_previous_id_defaults_to_none() -> None:
    """이전 Next Action id의 기본값은 없음이다.

    테스트 코드: AC-038
    """
    # when: 키 없이 만든 등록 요청을 입력으로 바꾼다
    data = _create().to_input()
    # then: 닫을 id가 없다
    assert data.close_previous_next_action_id is None


def test_close_previous_id_null_is_the_same_as_absent() -> None:
    """id가 null이면 없는 것과 같다.

    테스트 코드: AC-038
    """
    # when: null을 준 등록 요청과 키가 없는 등록 요청을 입력으로 바꾼다
    with_null = _create(close_previous_next_action_id=None).to_input()
    absent = _create().to_input()
    # then: 닫을 id가 없고 입력도 키가 없을 때와 같다
    assert with_null.close_previous_next_action_id is None
    assert with_null == absent


def test_close_previous_id_does_not_change_the_content_mapping() -> None:
    """닫을 id는 내용 변환에 영향을 주지 않는다."""
    # when: id를 실은 요청과 싣지 않은 요청을 입력으로 바꾼다
    with_id = _create(close_previous_next_action_id=7).to_input()
    without_id = _create().to_input()
    # then: 내용 변환은 같다
    assert with_id.content == without_id.content


@pytest.mark.parametrize("bad", ["7", 0, -1, 7.5, True, 2**53, [7], {"id": 7}])
def test_close_previous_id_rejects_non_positive_non_integer_and_out_of_range(bad: object) -> None:
    """양수 정수가 아니거나 범위를 벗어난 id는 거절한다.

    테스트 코드: AC-045
    """
    # when·then: 문자열·0·음수·소수·불리언·상한 초과·배열·객체를 주면 검증 오류다
    with pytest.raises(ValidationError):
        _create(close_previous_next_action_id=bad)


def test_the_update_request_does_not_accept_the_field() -> None:
    """수정 요청은 이 필드를 받지 않는다.

    테스트 코드: AC-054
    """
    # when·then: 수정 요청에 이 필드를 넣으면 검증 오류다
    with pytest.raises(ValidationError):
        DealActionUpdateRequest(**{**BODY, FIELD: 7})


def test_openapi_documents_an_optional_nullable_integer_on_create_only() -> None:
    """OpenAPI는 등록 요청에만 선택·null 허용 정수로 문서화한다.

    테스트 코드: AC-070
    """
    # when: OpenAPI 문서를 만든다
    spec = create_app(
        settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases()
    ).openapi()
    # then: 등록 요청에는 필수 아닌 정수·null 필드가 있고 수정 요청에는 없다
    schemas = spec["components"]["schemas"]

    create = schemas["DealActionCreateRequest"]
    prop = create["properties"][FIELD]
    assert FIELD not in create.get("required", [])
    assert {o.get("type") for o in prop["anyOf"]} == {"integer", "null"}
    assert prop["description"]
    assert FIELD not in schemas["DealActionUpdateRequest"]["properties"]
