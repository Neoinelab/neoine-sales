"""Action 요청 스키마(AC-01·02·05·10·15·16, 계획 7장): 길이 제약 없음, 서버가 채우는 값은 거부."""

from datetime import date
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

import pytest
from app.application.choice import CatalogChoice
from pydantic import ValidationError

from app.application.deal_action.inputs import (
    ActionContentInput,
    DealActionInput,
    StatusChangeInput,
)
from app.application.ports.deal_action_repository import DealActionQuery, DealActionSort
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.sync import SyncResolution
from app.web.schemas.deal_action import (
    DealActionCreateRequest,
    DealActionSearchParams,
    DealActionUpdateRequest,
)
from tests.factories import make_deal_code
from tests.support.user_ids import uid

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
        status_change=None,
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


@pytest.mark.parametrize("missing", ["action_type", "action", "next_action"])
def test_the_text_fields_and_type_are_required_in_the_body(missing: str) -> None:
    body = {key: value for key, value in BODY.items() if key != missing}

    with pytest.raises(ValidationError):
        DealActionUpdateRequest(**body)


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

    assert data.status_change == StatusChangeInput(field=field, value="best", resolution=None)


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

    assert data.status_change is not None
    assert data.status_change.resolution == SyncResolution(
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


def test_search_params_default_to_everything_sorted_latest_first() -> None:
    query = DealActionSearchParams().to_query("20261016-A001")

    assert query == DealActionQuery(deal_code=make_deal_code("A001"))
    assert query.sort is DealActionSort.ACTED_AT_DESC


def test_search_params_map_every_condition() -> None:
    email_id = uuid4()
    params = DealActionSearchParams(
        action_type_id=email_id,
        actor_user_id=uid("kim"),
        keyword=" 견적 ",
        acted_from="2026-10-01",
        acted_to="2026-10-31",
        due_from="2026-11-01",
        due_to="2026-11-30",
        sort="due_date_asc",
    )

    query = params.to_query("20261016-A001")

    assert query.deal_code == make_deal_code("A001")
    assert query.action_type_id == email_id
    assert query.actor_user_id == uid("kim")
    assert query.keyword == "견적"
    assert (query.acted_from, query.acted_to) == (date(2026, 10, 1), date(2026, 10, 31))
    assert (query.due_from, query.due_to) == (date(2026, 11, 1), date(2026, 11, 30))
    assert query.sort is DealActionSort.DUE_DATE_ASC


@pytest.mark.parametrize("sort", ["acted_at_desc", "acted_at_asc", "due_date_asc"])
def test_the_three_sorts_are_accepted(sort: str) -> None:
    assert DealActionSearchParams(sort=sort).sort.value == sort


@pytest.mark.parametrize("sort", ["due_date_desc", "created_asc", "DUE_DATE_ASC", ""])
def test_any_other_sort_is_rejected(sort: str) -> None:
    with pytest.raises(ValidationError):
        DealActionSearchParams(sort=sort)


@pytest.mark.parametrize(
    "params",
    [
        {"offset": 0},
        {"limit": 10},
        {"deal_code": "20261016-A001"},
        {"actor": "박영업"},
        {"unknown": "x"},
        {"actor_user_id": "not-a-uuid"},
        {"action_type": "meeting"},  # 구 파라미터(enum 값)는 모르는 파라미터다
        {"action_type_id": "not-a-uuid"},
        {"acted_from": "soon"},
        {"due_to": "2026-13-40"},
        {"keyword": "가" * 101},
    ],
)
def test_invalid_or_retired_search_params_are_rejected(params: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DealActionSearchParams(**params)


def test_a_malformed_deal_code_in_the_path_is_a_not_found() -> None:
    with pytest.raises(DealNotFoundError):
        DealActionSearchParams().to_query("not-a-code")
