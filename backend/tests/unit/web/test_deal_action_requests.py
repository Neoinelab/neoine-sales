"""Action 요청 스키마(AC-01·02·05·10·15·16, 계획 7장): 길이 제약 없음, 서버가 채우는 값은 거부."""

from datetime import date
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.application.choice import CatalogChoice
from app.application.deal_action.inputs import (
    ActionContentInput,
    DealActionInput,
    StatusChangeInput,
)
from app.domain.deal.sync import SyncResolution
from app.web.schemas.deal_action import (
    DealActionCreateRequest,
    DealActionUpdateRequest,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

BODY = {
    "action_type": {"name": "미팅"},
    "action": "킥오프 미팅",
    "next_action": "요구사항 문서 전달",
    "due_date": "2026-03-10",
    "memo": "요구사항 정리",
}


def _create(**overrides: object) -> DealActionCreateRequest:
    return DealActionCreateRequest(**{**BODY, **overrides})


def _update(**overrides: object) -> DealActionUpdateRequest:
    return DealActionUpdateRequest(**{**BODY, **overrides})


def test_create_request_maps_to_the_use_case_input_without_a_status_change() -> None:
    data = _create().to_input()

    assert data == DealActionInput(
        content=ActionContentInput(
            action_type=CatalogChoice(name="미팅"),
            action="킥오프 미팅",
            next_action="요구사항 문서 전달",
            due_date=date(2026, 3, 10),
            memo="요구사항 정리",
        ),
        status_changes=(),
    )


def test_update_request_maps_to_the_content_input() -> None:
    data = _update(memo="").to_input()

    assert data == ActionContentInput(
        action_type=CatalogChoice(name="미팅"),
        action="킥오프 미팅",
        next_action="요구사항 문서 전달",
        due_date=date(2026, 3, 10),
        memo="",
    )


@pytest.mark.parametrize("model", [DealActionCreateRequest, DealActionUpdateRequest])
@pytest.mark.parametrize(
    "extra",
    [
        {"acted_at": "2026-03-02T10:00:00+09:00"},
        {"actor_user_id": "00000000-0000-4000-8000-000000000001"},
        {"actor": "박영업"},
        {"deal_code": "20261016-A001"},
        {"title": "구 필드"},
        {"content": "구 필드"},
    ],
)
def test_server_filled_and_retired_fields_are_rejected(
    model: type[DealActionCreateRequest], extra: Mapping[str, object]
) -> None:
    with pytest.raises(ValidationError):
        model(**{**BODY, **extra})


def test_only_the_type_is_required_in_the_body() -> None:
    body = {key: value for key, value in BODY.items() if key != "action_type"}

    with pytest.raises(ValidationError):
        DealActionUpdateRequest(**body)


@pytest.mark.parametrize("model", [DealActionCreateRequest, DealActionUpdateRequest])
def test_progress_only_body_is_accepted_and_next_action_defaults_to_empty(
    model: type[DealActionCreateRequest],
) -> None:
    body = {"action_type": {"name": "미팅"}, "action": "통화만"}

    data = model(**body).to_input()
    content = data.content if isinstance(data, DealActionInput) else data

    assert content.action == "통화만"
    assert content.next_action == ""
    assert content.due_date is None


@pytest.mark.parametrize("model", [DealActionCreateRequest, DealActionUpdateRequest])
def test_next_only_body_is_accepted_and_progress_defaults_to_empty(
    model: type[DealActionCreateRequest],
) -> None:
    body = {"action_type": {"name": "미팅"}, "next_action": "견적", "due_date": "2026-03-10"}

    data = model(**body).to_input()
    content = data.content if isinstance(data, DealActionInput) else data

    assert content.action == ""
    assert content.next_action == "견적"
    assert content.due_date == date(2026, 3, 10)


def test_a_missing_or_null_due_date_reaches_the_domain_as_none() -> None:
    without = {key: value for key, value in BODY.items() if key != "due_date"}

    assert DealActionUpdateRequest(**without).to_input().due_date is None
    assert _update(due_date=None).to_input().due_date is None


@pytest.mark.parametrize("value", ["2026-13-40", "내일", "20260310x", 123])
def test_a_due_date_that_is_not_a_calendar_date_is_rejected(value: object) -> None:
    with pytest.raises(ValidationError):
        _update(due_date=value)


def test_memo_defaults_to_an_empty_string() -> None:
    without = {key: value for key, value in BODY.items() if key != "memo"}

    assert DealActionUpdateRequest(**without).to_input().memo == ""


def test_the_type_may_be_chosen_by_id() -> None:
    type_id = uuid4()

    data = _update(action_type={"id": str(type_id)}).to_input()

    assert data.action_type == CatalogChoice(id=type_id)


def test_the_type_name_is_passed_on_untouched_for_the_domain_to_judge() -> None:
    assert _update(action_type={"name": "  웨비나  "}).to_input().action_type == CatalogChoice(
        name="  웨비나  "
    )
    assert _update(action_type={"name": ""}).to_input().action_type == CatalogChoice(name="")


@pytest.mark.parametrize(
    "action_type",
    [
        pytest.param({"id": str(uuid4()), "name": "미팅"}, id="both"),
        pytest.param({}, id="neither"),
        pytest.param({"id": None, "name": None}, id="both-null"),
        pytest.param("meeting", id="old-enum-value"),
        pytest.param("미팅", id="plain-name-string"),
        pytest.param(None, id="null"),
        pytest.param({"id": "not-a-uuid"}, id="id-not-a-uuid"),
        pytest.param({"name": 3}, id="name-not-a-string"),
    ],
)
@pytest.mark.parametrize("model", [DealActionCreateRequest, DealActionUpdateRequest])
def test_an_invalid_type_choice_is_rejected(
    model: type[DealActionCreateRequest], action_type: object
) -> None:
    with pytest.raises(ValidationError):
        model(**{**BODY, "action_type": action_type})


def test_action_request_accepts_long_text_without_schema_limit() -> None:
    data = _create(action="가" * 5_000, next_action="나" * 5_000, memo="다" * 20_000).to_input()

    assert len(data.content.action) == 5_000
    assert len(data.content.next_action) == 5_000
    assert len(data.content.memo) == 20_000
    long_update = _update(action="가" * 5_000, memo="다" * 20_000).to_input()
    assert (len(long_update.action), len(long_update.memo)) == (5_000, 20_000)


def test_blank_texts_are_left_to_the_domain_messages() -> None:
    data = _update(action="   ", next_action="").to_input()

    assert (data.action, data.next_action) == ("   ", "")


@pytest.mark.parametrize("field", ["status_key", "forecast_key"])
def test_a_status_change_may_target_status_or_forecast(
    field: Literal["status_key", "forecast_key"],
) -> None:
    data = _create(status_change={"change": {"field": field, "value": "best"}}).to_input()

    assert data.status_changes == (StatusChangeInput(field=field, value="best", resolution=None),)


def test_a_status_change_maps_every_resolution_answer() -> None:
    data = _create(
        status_change={
            "change": {"field": "status_key", "value": "contract_completed"},
            "resolution": {
                "revenue_amount": 900_000_000,
                "revenue_date": "2026-10-20",
                "status_key": "poc_completed",
                "forecast_key": "best",
            },
        }
    ).to_input()

    assert len(data.status_changes) == 1
    assert data.status_changes[0].resolution == SyncResolution(
        revenue_amount=900_000_000,
        revenue_date=date(2026, 10, 20),
        status_key="poc_completed",
        forecast_key="best",
    )


@pytest.mark.parametrize("field", ["revenue_amount", "revenue_date", "name"])
def test_a_status_change_to_a_non_sync_field_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        _create(status_change={"change": {"field": field, "value": 1}})


def test_the_update_request_has_no_status_change() -> None:
    with pytest.raises(ValidationError):
        _update(status_change={"change": {"field": "status_key", "value": "best"}})
