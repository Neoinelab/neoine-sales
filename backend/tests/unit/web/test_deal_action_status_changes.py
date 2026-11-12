"""Action 등록 요청의 `status_changes`: 순서 유지, 형태 검증."""

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
    """status_changes는 순서를 지켜 입력으로 바뀐다.

    테스트 코드: AC-030
    """
    # when: Forecast 변경과 매출 답이 있는 Status 변경 순서로 입력으로 바꾼다
    data = _create(status_changes=[FORECAST_BEST, STATUS_CLOSE]).to_input()

    # then: 같은 순서의 변경 두 건이 담긴다
    assert data.status_changes == (
        StatusChangeInput(field="forecast_key", value="best", resolution=None),
        StatusChangeInput(
            field="status_key",
            value="contract_completed",
            resolution=SyncResolution(revenue_amount=900_000_000, revenue_date=date(2026, 10, 20)),
        ),
    )


def test_a_single_status_change_maps_to_a_one_item_tuple() -> None:
    """단건 status_change는 1건짜리 목록과 같다.

    테스트 코드: AC-034
    """
    # when: 단건 status_change를 입력으로 바꾼다
    data = _create(status_change=STATUS_INTRO).to_input()

    # then: 변경 한 건이 담긴다
    assert data.status_changes == (
        StatusChangeInput(field="status_key", value="introduction", resolution=None),
    )


@pytest.mark.parametrize("extra", [{}, {"status_changes": []}, {"status_changes": None}])
def test_no_or_empty_or_null_status_changes_mean_no_change(extra: dict[str, Any]) -> None:
    """변경이 없거나 빈 배열·null이면 변경 없음이다.

    테스트 코드: AC-034
    """
    # when·then: 키가 없거나 빈 배열이거나 null이면 변경이 없다
    assert _create(**extra).to_input().status_changes == ()


def test_both_status_change_forms_together_are_rejected() -> None:
    """단건과 목록을 함께 보내면 거절한다.

    테스트 코드: AC-034
    """
    # given: 각각은 유효한 본문
    assert _create(status_changes=[FORECAST_BEST]).to_input().status_changes  # 각각은 유효하다
    assert _create(status_change=STATUS_INTRO).to_input().status_changes
    with pytest.raises(ValidationError):
        # when·then: 둘을 함께 보내면 검증 오류다
        _create(status_change=STATUS_INTRO, status_changes=[FORECAST_BEST])


def test_both_forms_together_are_rejected_even_when_status_changes_is_empty() -> None:
    """status_changes가 빈 배열이어도 단건과 함께 보내면 거절한다.

    테스트 코드: AC-034
    """
    # given: 빈 배열은 단독으로 유효하다
    assert _create(status_changes=[]).to_input().status_changes == ()
    with pytest.raises(ValidationError):
        # when·then: 단건과 빈 배열을 함께 보내면 검증 오류다
        _create(status_change=STATUS_INTRO, status_changes=[])


def test_null_for_both_forms_is_accepted_as_no_change() -> None:
    """두 형식이 null이면 변경 없음으로 받는다.

    테스트 코드: AC-034
    """
    # when·then: 둘 다 null이면 변경이 없고 한쪽만 값이 있으면 변경이 있다
    assert _create(status_change=None, status_changes=None).to_input().status_changes == ()
    assert _create(status_change=STATUS_INTRO, status_changes=None).to_input().status_changes != ()
    assert (
        _create(status_change=None, status_changes=[STATUS_INTRO]).to_input().status_changes != ()
    )


def test_duplicate_fields_in_status_changes_are_rejected() -> None:
    """같은 필드를 두 번 바꾸는 목록은 거절한다.

    테스트 코드: AC-034
    """
    # given: 서로 다른 필드 두 건은 유효하다
    other = {"change": {"field": "status_key", "value": "poc_completed"}}
    assert len(_create(status_changes=[STATUS_INTRO, FORECAST_BEST]).to_input().status_changes) == 2
    # when·then: 같은 필드를 두 번 담으면 검증 오류다
    with pytest.raises(ValidationError):
        _create(status_changes=[STATUS_INTRO, other])


def test_more_than_two_status_changes_are_rejected() -> None:
    """변경이 3건 이상인 목록은 거절한다.

    테스트 코드: AC-034
    """
    # given: 두 건은 유효하다
    assert len(_create(status_changes=[STATUS_INTRO, FORECAST_BEST]).to_input().status_changes) == 2
    # when·then: 세 건을 담으면 검증 오류다
    with pytest.raises(ValidationError):
        _create(status_changes=[STATUS_INTRO, FORECAST_BEST, STATUS_INTRO])


@pytest.mark.parametrize("field", ["revenue_amount", "revenue_date", "name"])
def test_a_status_changes_item_with_a_non_sync_field_is_rejected(field: str) -> None:
    """Status·Forecast 외 필드를 대상으로 하는 항목은 거절한다.

    테스트 코드: AC-034
    """
    # given: Forecast 변경은 유효하다
    assert _create(status_changes=[FORECAST_BEST]).to_input().status_changes
    # when·then: 매출금액·매출일·이름을 대상으로 하면 검증 오류다
    with pytest.raises(ValidationError):
        _create(status_changes=[{"change": {"field": field, "value": 1}}])


def test_the_update_request_has_no_status_changes() -> None:
    """수정 요청에는 status_changes가 없다.

    테스트 코드: AC-054
    """
    # when·then: 수정 요청에 status_changes를 넣으면 검증 오류다
    with pytest.raises(ValidationError):
        DealActionUpdateRequest(**{**BODY, "status_changes": [STATUS_INTRO]})
