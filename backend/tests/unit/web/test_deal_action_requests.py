"""Action 요청 스키마: 길이 제약 없음, 서버가 채우는 값은 거부."""

from datetime import date
from typing import TYPE_CHECKING, Literal

import pytest
from pydantic import ValidationError

from app.application.choice import CatalogChoice
from app.application.deal_action import inputs as action_inputs
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
from tests.support.ids import MISSING_ID, new_id

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
    """등록 요청은 동반 변경 없는 유스케이스 입력으로 바뀐다."""
    # when: 등록 요청을 유스케이스 입력으로 바꾼다
    data = _create().to_input()

    # then: 내용이 그대로 담기고 동반 변경은 비어 있다
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
    """수정 요청은 내용 입력으로 바뀌고 수행일은 지정 없음이다."""
    # when: Memo가 빈 수정 요청을 입력으로 바꾼다
    data = _update(memo="").to_input()

    # then: 내용 칸이 담기고 수행일은 없다
    assert data == action_inputs.DealActionUpdateInput(
        content=ActionContentInput(
            action_type=CatalogChoice(name="미팅"),
            action="킥오프 미팅",
            next_action="요구사항 문서 전달",
            due_date=date(2026, 3, 10),
            memo="",
        ),
        acted_on=None,
    )


@pytest.mark.parametrize("model", [DealActionCreateRequest, DealActionUpdateRequest])
@pytest.mark.parametrize(
    "extra",
    [
        {"acted_at": "2026-03-02T10:00:00+09:00"},
        {"actor_user_id": MISSING_ID},
        {"actor": "박영업"},
        {"deal_code": "20261016-A001"},
        {"title": "구 필드"},
        {"content": "구 필드"},
    ],
)
def test_server_filled_and_retired_fields_are_rejected(
    model: type[DealActionCreateRequest], extra: Mapping[str, object]
) -> None:
    """서버가 채우는 값과 폐지된 필드를 보내면 거절한다.

    테스트 코드: AC-012
    """
    # when·then: 서버 필드나 예전 필드를 넣은 본문은 검증 오류다
    with pytest.raises(ValidationError):
        model(**{**BODY, **extra})


def test_only_the_type_is_required_in_the_body() -> None:
    """본문에서 필수는 유형뿐이다."""
    # given: 유형을 뺀 본문
    body = {key: value for key, value in BODY.items() if key != "action_type"}

    # when·then: 유형 없이 만들면 검증 오류다
    with pytest.raises(ValidationError):
        DealActionUpdateRequest(**body)


@pytest.mark.parametrize("model", [DealActionCreateRequest, DealActionUpdateRequest])
def test_progress_only_body_is_accepted_and_next_action_defaults_to_empty(
    model: type[DealActionCreateRequest],
) -> None:
    """진행사항만 있는 본문은 받고 Next Action은 빈 값이 된다.

    테스트 코드: AC-006
    """
    # given: 유형과 진행사항만 있는 본문
    body = {"action_type": {"name": "미팅"}, "action": "통화만"}

    # when: 입력으로 바꾼다
    data = model(**body).to_input()
    content = data.content

    # then: 진행사항은 그대로이고 Next Action은 빈 값, Due는 없다
    assert content.action == "통화만"
    assert content.next_action == ""
    assert content.due_date is None


@pytest.mark.parametrize("model", [DealActionCreateRequest, DealActionUpdateRequest])
def test_next_only_body_is_accepted_and_progress_defaults_to_empty(
    model: type[DealActionCreateRequest],
) -> None:
    """Next Action만 있는 본문은 받고 진행사항은 빈 값이 된다.

    테스트 코드: AC-007
    """
    # given: 유형과 Next Action·Due만 있는 본문
    body = {"action_type": {"name": "미팅"}, "next_action": "견적", "due_date": "2026-03-10"}

    # when: 입력으로 바꾼다
    data = model(**body).to_input()
    content = data.content

    # then: 진행사항은 빈 값이고 Next Action·Due는 그대로다
    assert content.action == ""
    assert content.next_action == "견적"
    assert content.due_date == date(2026, 3, 10)


def test_a_missing_or_null_due_date_reaches_the_domain_as_none() -> None:
    """Due Date가 없거나 null이면 도메인에는 없음으로 간다.

    테스트 코드: AC-009
    """
    # given: Due Date 키가 없는 본문
    without = {key: value for key, value in BODY.items() if key != "due_date"}

    # when·then: 키가 없을 때와 null일 때 모두 Due 없음이다
    assert DealActionUpdateRequest(**without).to_input().content.due_date is None
    assert _update(due_date=None).to_input().content.due_date is None


@pytest.mark.parametrize("value", ["2026-13-40", "내일", "20260310x", 123])
def test_a_due_date_that_is_not_a_calendar_date_is_rejected(value: object) -> None:
    """달력 날짜가 아닌 Due Date는 검증 오류다.

    테스트 코드: AC-012
    """
    # when·then: 달력에 없는 값·글자·숫자를 Due로 주면 검증 오류다
    with pytest.raises(ValidationError):
        _update(due_date=value)


def test_memo_defaults_to_an_empty_string() -> None:
    """Memo를 생략하면 빈 문자열이다.

    테스트 코드: AC-005
    """
    # given: Memo 키가 없는 본문
    without = {key: value for key, value in BODY.items() if key != "memo"}

    # when·then: 입력의 Memo는 빈 문자열이다
    assert DealActionUpdateRequest(**without).to_input().content.memo == ""


def test_the_type_may_be_chosen_by_id() -> None:
    """유형은 id로 고를 수 있다."""
    # given: 유형 id
    type_id = new_id()

    # when: id로 고른 본문을 입력으로 바꾼다
    data = _update(action_type={"id": type_id}).to_input()

    # then: 선택은 id 하나다
    assert data.content.action_type == CatalogChoice(id=type_id)


def test_the_type_name_is_passed_on_untouched_for_the_domain_to_judge() -> None:
    """유형 이름은 도메인이 판정하도록 그대로 넘긴다."""
    # when·then: 공백이 낀 이름과 빈 이름이 가공 없이 선택으로 넘어간다
    assert _update(
        action_type={"name": "  웨비나  "}
    ).to_input().content.action_type == CatalogChoice(name="  웨비나  ")
    assert _update(action_type={"name": ""}).to_input().content.action_type == CatalogChoice(
        name=""
    )


@pytest.mark.parametrize(
    "action_type",
    [
        pytest.param({"id": MISSING_ID, "name": "미팅"}, id="both"),
        pytest.param({}, id="neither"),
        pytest.param({"id": None, "name": None}, id="both-null"),
        pytest.param("meeting", id="old-enum-value"),
        pytest.param("미팅", id="plain-name-string"),
        pytest.param(None, id="null"),
        pytest.param({"id": "not-an-id"}, id="id-not-an-id"),
        pytest.param({"id": "5"}, id="id-as-a-string"),
        pytest.param({"id": True}, id="id-as-a-boolean"),
        pytest.param({"id": 5.0}, id="id-as-a-float"),
        pytest.param({"id": 0}, id="id-zero"),
        pytest.param({"id": -3}, id="id-negative"),
        pytest.param({"id": 2**53}, id="id-above-the-limit"),
        pytest.param({"name": 3}, id="name-not-a-string"),
    ],
)
@pytest.mark.parametrize("model", [DealActionCreateRequest, DealActionUpdateRequest])
def test_an_invalid_type_choice_is_rejected(
    model: type[DealActionCreateRequest], action_type: object
) -> None:
    """잘못된 유형 선택 형식은 검증 오류다."""
    # when·then: id와 이름을 함께 주거나 빈 값·문자열·잘못된 id를 주면 검증 오류다
    with pytest.raises(ValidationError):
        model(**{**BODY, "action_type": action_type})


def test_action_request_accepts_long_text_without_schema_limit() -> None:
    """요청 스키마는 길이 상한 없이 긴 텍스트를 받는다.

    테스트 코드: AC-004
    """
    # when: 5,000자·5,000자·20,000자 본문을 입력으로 바꾼다
    data = _create(action="가" * 5_000, next_action="나" * 5_000, memo="다" * 20_000).to_input()

    # then: 길이가 그대로다
    assert len(data.content.action) == 5_000
    assert len(data.content.next_action) == 5_000
    assert len(data.content.memo) == 20_000
    # when: 수정 요청도 긴 텍스트로 입력으로 바꾼다
    long_update = _update(action="가" * 5_000, memo="다" * 20_000).to_input()
    # then: 길이가 그대로다
    assert (len(long_update.content.action), len(long_update.content.memo)) == (5_000, 20_000)


def test_blank_texts_are_left_to_the_domain_messages() -> None:
    """빈 텍스트는 스키마가 아니라 도메인 문구로 판정한다.

    테스트 코드: AC-008
    """
    # when: 공백뿐인 진행사항과 빈 Next Action으로 입력을 만든다
    data = _update(action="   ", next_action="").to_input()

    # then: 값이 가공 없이 넘어간다
    assert (data.content.action, data.content.next_action) == ("   ", "")


@pytest.mark.parametrize("field", ["status_key", "forecast_key"])
def test_a_status_change_may_target_status_or_forecast(
    field: Literal["status_key", "forecast_key"],
) -> None:
    """동반 변경은 Status나 Forecast를 대상으로 할 수 있다.

    테스트 코드: AC-034
    """
    # when: 단건 동반 변경이 있는 요청을 입력으로 바꾼다
    data = _create(status_change={"change": {"field": field, "value": "best"}}).to_input()

    # then: 변경 한 건이 담긴다
    assert data.status_changes == (StatusChangeInput(field=field, value="best", resolution=None),)


def test_a_status_change_maps_every_resolution_answer() -> None:
    """동반 변경의 모든 답이 입력에 담긴다.

    테스트 코드: AC-034
    """
    # when: 매출·Status·Forecast 답이 모두 있는 동반 변경을 입력으로 바꾼다
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

    # then: 답이 모두 담긴다
    assert len(data.status_changes) == 1
    assert data.status_changes[0].resolution == SyncResolution(
        revenue_amount=900_000_000,
        revenue_date=date(2026, 10, 20),
        status_key="poc_completed",
        forecast_key="best",
    )


@pytest.mark.parametrize("field", ["revenue_amount", "revenue_date", "name"])
def test_a_status_change_to_a_non_sync_field_is_rejected(field: str) -> None:
    """Status·Forecast 외 필드를 대상으로 하는 동반 변경은 거절한다.

    테스트 코드: AC-034
    """
    # when·then: 매출금액·매출일·이름을 대상으로 하면 검증 오류다
    with pytest.raises(ValidationError):
        _create(status_change={"change": {"field": field, "value": 1}})


def test_the_update_request_has_no_status_change() -> None:
    """수정 요청에는 동반 변경이 없다.

    테스트 코드: AC-054
    """
    # when·then: 수정 요청에 동반 변경을 넣으면 검증 오류다
    with pytest.raises(ValidationError):
        _update(status_change={"change": {"field": "status_key", "value": "best"}})
