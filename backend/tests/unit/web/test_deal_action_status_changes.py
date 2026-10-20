"""Action 등록 요청의 `status_changes`(AC-01·05·08·11): 순서 유지, 형태 검증."""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.application.deal_action.inputs import StatusChangeInput
from app.domain.deal.sync import SyncResolution
from app.web.schemas.deal_action import DealActionCreateRequest, DealActionUpdateRequest

BODY = {
    "action_type": {"name": "미팅"},
    "action": "킥오프 미팅",
    "next_action": "요구사항 문서 전달",
    "due_date": "2026-03-10",
    "memo": "",
}
FORECAST_BEST = {"change": {"field": "forecast_key", "value": "best"}}
STATUS_INTRO = {"change": {"field": "status_key", "value": "introduction"}}
STATUS_CLOSE = {
    "change": {"field": "status_key", "value": "contract_completed"},
    "resolution": {"revenue_amount": 900_000_000, "revenue_date": "2026-10-20"},
}


def _create(**overrides: Any) -> DealActionCreateRequest:  # noqa: ANN401
    return DealActionCreateRequest(**{**BODY, **overrides})


def test_status_changes_map_to_the_input_in_order() -> None:
    data = _create(status_changes=[FORECAST_BEST, STATUS_CLOSE]).to_input()

    assert data.status_changes == (
        StatusChangeInput(field="forecast_key", value="best", resolution=None),
        StatusChangeInput(
            field="status_key",
            value="contract_completed",
            resolution=SyncResolution(revenue_amount=900_000_000, revenue_date=date(2026, 10, 20)),
        ),
    )


def test_a_single_status_change_maps_to_a_one_item_tuple() -> None:
    data = _create(status_change=STATUS_INTRO).to_input()

    assert data.status_changes == (
        StatusChangeInput(field="status_key", value="introduction", resolution=None),
    )


@pytest.mark.parametrize("extra", [{}, {"status_changes": []}, {"status_changes": None}])
def test_no_or_empty_or_null_status_changes_mean_no_change(extra: dict[str, Any]) -> None:
    assert _create(**extra).to_input().status_changes == ()


def test_both_status_change_forms_together_are_rejected() -> None:
    assert _create(status_changes=[FORECAST_BEST]).to_input().status_changes  # 각각은 유효하다
    assert _create(status_change=STATUS_INTRO).to_input().status_changes
    with pytest.raises(ValidationError):
        _create(status_change=STATUS_INTRO, status_changes=[FORECAST_BEST])


def test_both_forms_together_are_rejected_even_when_status_changes_is_empty() -> None:
    assert _create(status_changes=[]).to_input().status_changes == ()
    with pytest.raises(ValidationError):
        _create(status_change=STATUS_INTRO, status_changes=[])


def test_null_for_both_forms_is_accepted_as_no_change() -> None:
    assert _create(status_change=None, status_changes=None).to_input().status_changes == ()
    assert _create(status_change=STATUS_INTRO, status_changes=None).to_input().status_changes != ()
    assert (
        _create(status_change=None, status_changes=[STATUS_INTRO]).to_input().status_changes != ()
    )


def test_duplicate_fields_in_status_changes_are_rejected() -> None:
    other = {"change": {"field": "status_key", "value": "poc_completed"}}
    assert len(_create(status_changes=[STATUS_INTRO, FORECAST_BEST]).to_input().status_changes) == 2
    with pytest.raises(ValidationError):
        _create(status_changes=[STATUS_INTRO, other])


def test_more_than_two_status_changes_are_rejected() -> None:
    assert len(_create(status_changes=[STATUS_INTRO, FORECAST_BEST]).to_input().status_changes) == 2
    with pytest.raises(ValidationError):
        _create(status_changes=[STATUS_INTRO, FORECAST_BEST, STATUS_INTRO])


@pytest.mark.parametrize("field", ["revenue_amount", "revenue_date", "name"])
def test_a_status_changes_item_with_a_non_sync_field_is_rejected(field: str) -> None:
    assert _create(status_changes=[FORECAST_BEST]).to_input().status_changes
    with pytest.raises(ValidationError):
        _create(status_changes=[{"change": {"field": field, "value": 1}}])


def test_the_update_request_has_no_status_changes() -> None:
    with pytest.raises(ValidationError):
        DealActionUpdateRequest(**{**BODY, "status_changes": [STATUS_INTRO]})
