"""POST /deals/{code}/changes 요청 스키마(R3, AC-19, 계획 7장): 한 번에 값 하나만 바꾼다.

본문은 `{change: {field, value}, resolution?: {...}}`이고 field로 value의 형식이 정해진다.
금액·날짜의 범위/유효성은 도메인 문구가 나가도록 스키마에 두지 않는다(0도 파싱은 된다).
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from app.application.deal.inputs import DealChangeInput
from app.domain.deal.sync import SyncResolution
from app.web.schemas.deal import DealChangeRequest

if TYPE_CHECKING:
    from collections.abc import Mapping


def _request(change: Mapping[str, object], **rest: object) -> DealChangeRequest:
    return DealChangeRequest(**{"change": change, **rest})


def test_a_status_change_maps_to_the_use_case_input() -> None:
    data = _request({"field": "status_key", "value": "contract_completed"}).to_input()

    assert data == DealChangeInput(field="status_key", value="contract_completed", resolution=None)


def test_a_forecast_change_with_a_resolution_maps_every_answer() -> None:
    data = _request(
        {"field": "forecast_key", "value": "won"},
        resolution={
            "revenue_amount": 900_000_000,
            "revenue_date": "2026-10-20",
            "status_key": "poc_completed",
            "forecast_key": "best",
        },
    ).to_input()

    assert data.field == "forecast_key"
    assert data.value == "won"
    assert data.resolution == SyncResolution(
        revenue_amount=900_000_000,
        revenue_date=date(2026, 10, 20),
        status_key="poc_completed",
        forecast_key="best",
    )


def test_an_amount_change_has_an_integer_value() -> None:
    data = _request({"field": "revenue_amount", "value": 1_870_000_000}).to_input()

    assert (data.field, data.value) == ("revenue_amount", 1_870_000_000)


def test_an_expected_close_change_has_a_date_value() -> None:
    data = _request({"field": "revenue_date", "value": "2026-12-31"}).to_input()

    assert (data.field, data.value) == ("revenue_date", date(2026, 12, 31))


@pytest.mark.parametrize("amount", [0, -5, 2**53])
def test_amount_range_is_left_to_the_domain(amount: int) -> None:
    assert _request({"field": "revenue_amount", "value": amount}).to_input().value == amount


def test_a_partial_resolution_leaves_the_other_answers_empty() -> None:
    data = _request(
        {"field": "forecast_key", "value": "commit"}, resolution={"status_key": "poc_completed"}
    ).to_input()

    assert data.resolution == SyncResolution(status_key="poc_completed")


def test_a_null_or_missing_resolution_is_none() -> None:
    change = {"field": "forecast_key", "value": "best"}

    assert _request(change).to_input().resolution is None
    assert _request(change, resolution=None).to_input().resolution is None


@pytest.mark.parametrize(
    "change",
    [
        {"field": "name", "value": "x"},  # 바꿀 수 있는 필드가 아니다
        {"field": "owner_user_id", "value": "x"},
        {"field": "status_key", "value": 5},  # 코드 key는 문자열
        {"field": "revenue_amount", "value": "100"},  # 문자열 금액 거부
        {"field": "revenue_amount", "value": 1.5},
        {"field": "revenue_amount", "value": True},
        {"field": "revenue_date", "value": "2026/12/31"},
        {"field": "status_key"},
        {"value": "x"},
        {},
    ],
)
def test_a_malformed_change_is_rejected(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _request(change)


def test_users_is_not_a_changeable_field() -> None:
    with pytest.raises(ValidationError):
        _request({"field": "users", "value": 10})


@pytest.mark.parametrize(
    "resolution",
    [
        {"revenue_amount": "100"},
        {"revenue_amount": 1.5},
        {"revenue_date": "2026/10/20"},
        {"status_key": 3},
        {"unknown": "x"},
    ],
)
def test_a_malformed_resolution_is_rejected(resolution: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _request({"field": "forecast_key", "value": "won"}, resolution=resolution)


def test_the_change_is_required_and_other_body_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        DealChangeRequest()  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        _request({"field": "status_key", "value": "x"}, extra="nope")
