"""Action 유형 요청·응답 스키마(AC-1·2): 응답 항목의 키, 생성자·사용 수, 이름 요청."""

from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.application.action_type.dto import ActionTypeUsage
from app.web.schemas.action_type import (
    ActionTypeNameRequest,
    ActionTypeResponse,
    action_type_responses,
)
from tests.factories_action_type import make_action_type
from tests.fakes.use_cases import FakeUseCases

RESPONSE_KEYS = {
    "id",
    "name",
    "is_default",
    "created_by",
    "usage_count",
    "created_at",
    "updated_at",
}


async def test_response_includes_usage_and_creator() -> None:
    use_cases = FakeUseCases()
    creator = await use_cases.seed_user("kim", display_name="김영업")
    custom = make_action_type("웨비나", created_by=creator.id)

    items = await action_type_responses(use_cases, [ActionTypeUsage(custom, 4)])

    (item,) = items
    body = item.model_dump(mode="json")
    assert set(body) == RESPONSE_KEYS
    assert (body["name"], body["is_default"], body["usage_count"]) == ("웨비나", False, 4)
    assert body["created_by"]["id"] == creator.id
    assert body["id"] == custom.id
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None


async def test_action_type_ids_are_json_integers() -> None:
    use_cases = FakeUseCases()
    creator = await use_cases.seed_user("kim", display_name="김영업")
    custom = make_action_type("웨비나", created_by=creator.id)

    (item,) = await action_type_responses(use_cases, [ActionTypeUsage(custom, 4)])

    body = item.model_dump(mode="json")
    assert type(body["id"]) is int
    assert type(body["created_by"]["id"]) is int


async def test_a_default_type_has_no_creator() -> None:
    default = make_action_type("미팅", is_default=True, default_order=2)

    (item,) = await action_type_responses(FakeUseCases(), [ActionTypeUsage(default, 0)])

    body: dict[str, Any] = item.model_dump(mode="json")
    assert (body["is_default"], body["created_by"]) == (True, None)


async def test_responses_keep_the_given_order() -> None:
    types = [make_action_type(name) for name in ("가", "나", "다")]

    items = await action_type_responses(FakeUseCases(), [ActionTypeUsage(t, 0) for t in types])

    assert [i.name for i in items] == ["가", "나", "다"]


def test_the_response_model_is_the_documented_one() -> None:
    assert set(ActionTypeResponse.model_fields) == RESPONSE_KEYS


def test_the_name_request_takes_only_a_name() -> None:
    assert ActionTypeNameRequest(name="  웨비나 ").name == "  웨비나 "  # 정규화는 도메인 몫
    with pytest.raises(ValidationError):
        ActionTypeNameRequest.model_validate({})
    with pytest.raises(ValidationError):
        ActionTypeNameRequest.model_validate({"name": "x", "is_default": True})
