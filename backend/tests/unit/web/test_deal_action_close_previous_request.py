"""Action 생성 요청의 선택 필드 close_previous_next_action_id(R4 AC4-1·4-2, 하위 호환).

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
from tests.functional.conftest import make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
BODY: dict[str, Any] = {
    "action_type": {"name": "미팅"},
    "action": "킥오프 미팅",
    "next_action": "요구사항 문서 전달",
    "due_date": "2026-03-10",
    "memo": "",
}
FIELD = "close_previous_next_action_id"


def _create(**extra: object) -> DealActionCreateRequest:
    return DealActionCreateRequest(**{**BODY, **extra})


def test_close_previous_id_maps_to_input() -> None:
    data = _create(close_previous_next_action_id=7).to_input()

    assert isinstance(data, DealActionInput)
    assert data.close_previous_next_action_id == DealActionId(7)


def test_close_previous_id_defaults_to_none() -> None:
    assert _create().to_input().close_previous_next_action_id is None


def test_close_previous_id_null_is_the_same_as_absent() -> None:
    assert (
        _create(close_previous_next_action_id=None).to_input().close_previous_next_action_id is None
    )
    assert _create(close_previous_next_action_id=None).to_input() == _create().to_input()


def test_close_previous_id_does_not_change_the_content_mapping() -> None:
    assert (
        _create(close_previous_next_action_id=7).to_input().content == _create().to_input().content
    )


@pytest.mark.parametrize("bad", ["7", 0, -1, 7.5, True, 2**53, [7], {"id": 7}])
def test_close_previous_id_rejects_non_positive_non_integer_and_out_of_range(bad: object) -> None:
    with pytest.raises(ValidationError):
        _create(close_previous_next_action_id=bad)


def test_the_update_request_does_not_accept_the_field() -> None:
    with pytest.raises(ValidationError):
        DealActionUpdateRequest(**{**BODY, FIELD: 7})


def test_openapi_documents_an_optional_nullable_integer_on_create_only() -> None:
    spec = create_app(
        settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases()
    ).openapi()
    schemas = spec["components"]["schemas"]

    create = schemas["DealActionCreateRequest"]
    prop = create["properties"][FIELD]
    assert FIELD not in create.get("required", [])
    assert {o.get("type") for o in prop["anyOf"]} == {"integer", "null"}
    assert prop["description"]
    assert FIELD not in schemas["DealActionUpdateRequest"]["properties"]
