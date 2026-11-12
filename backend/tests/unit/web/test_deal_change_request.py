"""POST /deals/{code}/changes 요청 스키마(R3, 계획 7장): 한 번에 값 하나만 바꾼다.

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
    """Status 변경 본문은 유스케이스 입력으로 그대로 옮겨진다."""
    # when: Status 변경 요청을 입력으로 바꾼다
    data = _request({"field": "status_key", "value": "contract_completed"}).to_input()

    # then: 필드·값이 같고 resolution은 없다
    assert data == DealChangeInput(field="status_key", value="contract_completed", resolution=None)


def test_a_forecast_change_with_a_resolution_maps_every_answer() -> None:
    """resolution의 네 답이 모두 유스케이스 입력에 옮겨진다.

    테스트 코드: DD-031
    """
    # when: 매출·Status·Forecast 답이 모두 든 요청을 입력으로 바꾼다
    data = _request(
        {"field": "forecast_key", "value": "won"},
        resolution={
            "revenue_amount": 900_000_000,
            "revenue_date": "2026-10-20",
            "status_key": "poc_completed",
            "forecast_key": "best",
        },
    ).to_input()

    # then: 필드·값과 네 답(매출날짜는 날짜)이 같다
    assert data.field == "forecast_key"
    assert data.value == "won"
    assert data.resolution == SyncResolution(
        revenue_amount=900_000_000,
        revenue_date=date(2026, 10, 20),
        status_key="poc_completed",
        forecast_key="best",
    )


def test_an_amount_change_has_an_integer_value() -> None:
    """금액 변경의 값은 정수다.

    테스트 코드: DD-031
    """
    # when: 금액 변경 요청을 입력으로 바꾼다
    data = _request({"field": "revenue_amount", "value": 1_870_000_000}).to_input()

    # then: 필드와 정수 값이 같다
    assert (data.field, data.value) == ("revenue_amount", 1_870_000_000)


def test_an_expected_close_change_has_a_date_value() -> None:
    """Expected Close 변경의 값은 날짜다.

    테스트 코드: DD-031
    """
    # when: 날짜 변경 요청을 입력으로 바꾼다
    data = _request({"field": "revenue_date", "value": "2026-12-31"}).to_input()

    # then: 필드와 날짜 값이 같다
    assert (data.field, data.value) == ("revenue_date", date(2026, 12, 31))


@pytest.mark.parametrize("amount", [0, -5, 2**53])
def test_amount_range_is_left_to_the_domain(amount: int) -> None:
    """금액 범위(0·음수·2^53)는 스키마가 아니라 도메인이 판정하도록 통과시킨다.

    테스트 코드: DD-028
    """
    # when: 범위 밖 금액 변경 요청을 입력으로 바꾼다
    value = _request({"field": "revenue_amount", "value": amount}).to_input().value
    # then: 오류 없이 그 값이 그대로다
    assert value == amount


def test_a_partial_resolution_leaves_the_other_answers_empty() -> None:
    """일부 답만 준 resolution은 나머지 답이 비어 있다.

    테스트 코드: DD-031
    """
    # when: Status 답만 든 요청을 입력으로 바꾼다
    data = _request(
        {"field": "forecast_key", "value": "commit"},
        resolution={"status_key": "poc_completed"},
    ).to_input()

    # then: Status 답만 있다
    assert data.resolution == SyncResolution(status_key="poc_completed")


def test_a_null_or_missing_resolution_is_none() -> None:
    """resolution이 null이거나 없으면 입력의 resolution도 없다.

    테스트 코드: DD-031
    """
    # given: resolution이 없는 Forecast 변경
    change = {"field": "forecast_key", "value": "best"}

    # when: 생략한 요청과 null로 준 요청을 입력으로 바꾼다
    assert _request(change).to_input().resolution is None
    # then: 둘 다 resolution이 None이다
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
    """바꿀 수 없는 필드·형식이 틀린 값·누락은 요청 검증에서 거절된다.

    테스트 코드: DD-031
    """
    # when·then: 형식이 틀린 change로 요청을 만든다 → 검증 오류가 난다
    with pytest.raises(ValidationError):
        _request(change)


def test_users_is_not_a_changeable_field() -> None:
    """users는 단일 변경으로 바꿀 수 없는 필드다.

    테스트 코드: DD-031
    """
    # when·then: users 변경 요청을 만든다 → 검증 오류가 난다
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
    """resolution의 형식 오류와 모르는 키는 요청 검증에서 거절된다.

    테스트 코드: DD-031
    """
    # when·then: 형식이 틀린 resolution으로 요청을 만든다 → 검증 오류가 난다
    with pytest.raises(ValidationError):
        _request({"field": "forecast_key", "value": "won"}, resolution=resolution)


def test_the_change_is_required_and_other_body_keys_are_rejected() -> None:
    """change는 필수이고 모르는 본문 키는 거절된다.

    테스트 코드: DD-031
    """
    # when: change 없이, 모르는 키를 더해 요청을 만든다
    with pytest.raises(ValidationError):
        DealChangeRequest()  # type: ignore[call-arg]
    # then: 두 경우 모두 검증 오류가 난다
    with pytest.raises(ValidationError):
        _request({"field": "status_key", "value": "x"}, extra="nope")
