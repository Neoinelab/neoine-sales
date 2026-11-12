"""순차 동기화(`finalize_sequence`): 두 번째 변경은 첫 변경 적용 후 상태로 판정한다."""

from datetime import date

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal.sync import (
    SYNC_CONFLICT_MESSAGE,
    SYNC_DUPLICATE_MESSAGE,
    CoChange,
    SyncChange,
    SyncField,
    SyncResolution,
    SyncState,
    SyncStep,
    finalize_plan,
    finalize_sequence,
    plan_change,
)
from tests.support.expect import raises_with
from tests.support.sync_catalog import WON, default_catalog

CATALOG = default_catalog()
START = SyncState("prospecting", "pipeline")
LOST = SyncState("prospecting", "lost")
CLOSING = SyncResolution(revenue_amount=900_000_000, revenue_date=date(2026, 10, 20))
REVENUE_REQUIRED = "Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다."
CHOICE_REQUIRED = "함께 바꿀 값을 선택하세요."


def _status(value: str, resolution: SyncResolution | None = None) -> SyncStep:
    return SyncStep(SyncChange(SyncField.STATUS, value), resolution)


def _forecast(value: str, resolution: SyncResolution | None = None) -> SyncStep:
    return SyncStep(SyncChange(SyncField.FORECAST, value), resolution)


def test_no_steps_returns_nothing() -> None:
    """변경이 없으면 결과도 없다.

    테스트 코드: AC-034
    """
    # when·then: 빈 변경 목록을 확정하면 빈 결과다
    assert finalize_sequence(START, [], CATALOG) == ()


def test_a_single_step_equals_finalize_plan() -> None:
    """변경 하나는 단건 확정과 같은 결과다.

    테스트 코드: AC-034
    """
    # given: 계약완료 변경 하나와 그 계획
    step = _status("contract_completed", CLOSING)
    plan = plan_change(START, step.change, CATALOG)

    # when: 순차 확정을 한다
    applied = finalize_sequence(START, [step], CATALOG)

    # then: 단건 확정 결과와 같다
    assert applied == (finalize_plan(START, plan, CLOSING, CATALOG),)


def test_two_independent_steps_accumulate_states() -> None:
    """서로 독립인 두 변경은 상태를 차례로 쌓는다.

    테스트 코드: AC-030
    """
    # when: Status 제품소개, Forecast Best 순서로 확정한다
    applied = finalize_sequence(START, [_status("introduction"), _forecast("best")], CATALOG)

    # then: 단계마다 상태가 쌓이고 함께 변경은 없다
    assert [a.state for a in applied] == [
        SyncState("introduction", "pipeline"),
        SyncState("introduction", "best"),
    ]
    assert [a.co_changed for a in applied] == [(), ()]


def test_the_second_step_is_judged_after_the_first() -> None:
    """두 번째 변경은 첫 변경을 적용한 상태로 판정한다.

    테스트 코드: AC-031
    """
    # given: 종결(Won) 상태에서 Forecast Commit(답 PoC완료) 뒤 Status 제품소개
    steps = [
        _forecast("commit", SyncResolution(status_key="poc_completed")),
        _status("introduction"),
    ]

    # when: 순차 확정을 한다
    applied = finalize_sequence(WON, steps, CATALOG)

    # then: 두 번째 결과는 제품소개·Commit이고 함께 변경·알림이 없다
    assert applied[1].state == SyncState("introduction", "commit")
    assert applied[1].co_changed == ()
    assert applied[1].notice is None


def test_the_second_step_may_change_a_co_changed_field() -> None:
    """두 번째 변경은 첫 변경이 함께 바꾼 필드를 바꿀 수 있다.

    테스트 코드: AC-031
    """
    # given: Won에서 Status PoC완료(Forecast Commit 선택) 뒤 Forecast Best
    steps = [_status("poc_completed", SyncResolution(forecast_key="commit")), _forecast("best")]

    # when: 순차 확정을 한다
    applied = finalize_sequence(WON, steps, CATALOG)

    # then: 두 번째 결과는 PoC완료·Best이고 첫 단계의 함께 변경만 기록된다
    assert applied[1].state == SyncState("poc_completed", "best")
    assert applied[0].co_changed == (CoChange(SyncField.FORECAST, "won", "commit"),)
    assert applied[1].co_changed == ()


def test_closing_after_a_status_change_is_a_conflict() -> None:
    """Status를 바꾼 뒤 Forecast를 Won으로 종결하면 충돌이다.

    테스트 코드: AC-032
    """
    # when·then: Status 제품소개 뒤 Forecast Won을 확정하면 충돌 문구다
    with raises_with(InvalidValueError, SYNC_CONFLICT_MESSAGE):
        finalize_sequence(START, [_status("introduction"), _forecast("won", CLOSING)], CATALOG)


def test_reopening_after_closing_is_a_conflict() -> None:
    """종결한 뒤 되돌리는 변경은 충돌이다.

    테스트 코드: AC-032
    """
    # given: Status 계약완료로 종결한 뒤 Forecast Commit으로 되돌리는 변경
    steps = [
        _status("contract_completed", CLOSING),
        _forecast("commit", SyncResolution(status_key="poc_completed")),
    ]

    # when·then: 순차 확정을 하면 충돌 문구다
    with raises_with(InvalidValueError, SYNC_CONFLICT_MESSAGE):
        finalize_sequence(START, steps, CATALOG)


def test_closing_by_status_after_a_forecast_change_is_a_conflict() -> None:
    """Forecast를 바꾼 뒤 Status로 종결하면 충돌이다.

    테스트 코드: AC-032
    """
    # when·then: Forecast Best 뒤 Status 계약완료를 확정하면 충돌 문구다
    with raises_with(InvalidValueError, SYNC_CONFLICT_MESSAGE):
        finalize_sequence(
            START, [_forecast("best"), _status("contract_completed", CLOSING)], CATALOG
        )


def test_leaving_won_after_choosing_won_is_a_conflict() -> None:
    """Won을 고른 뒤 Won에서 벗어나는 변경은 충돌이다.

    테스트 코드: AC-032
    """
    # given: Forecast Won으로 종결한 뒤 Status PoC완료로 벗어나는 변경
    steps = [
        _forecast("won", CLOSING),
        _status("poc_completed", SyncResolution(forecast_key="commit")),
    ]

    # when·then: 순차 확정을 하면 충돌 문구다
    with raises_with(InvalidValueError, SYNC_CONFLICT_MESSAGE):
        finalize_sequence(START, steps, CATALOG)


def test_choosing_the_first_value_again_in_a_lost_reopen_is_allowed() -> None:
    """Lost 되돌림에서 첫 변경과 같은 값을 다시 고르는 것은 허용된다.

    테스트 코드: AC-031
    """
    # given: Lost 상태에서 Status 제품소개 뒤 Forecast Commit(답 제품소개)
    steps = [
        _status("introduction"),
        _forecast("commit", SyncResolution(status_key="introduction")),
    ]

    # when: 순차 확정을 한다
    applied = finalize_sequence(LOST, steps, CATALOG)

    # then: 두 번째 결과는 제품소개·Commit이다
    assert applied[1].state == SyncState("introduction", "commit")


def test_choosing_another_status_in_a_lost_reopen_is_a_conflict() -> None:
    """Lost 되돌림에서 첫 변경과 다른 Status를 고르면 충돌이다.

    테스트 코드: AC-032
    """
    # given: Lost 상태에서 Status 제품소개 뒤 Forecast Commit(답 기회발굴)
    steps = [_status("introduction"), _forecast("commit", SyncResolution(status_key="prospecting"))]

    # when·then: 순차 확정을 하면 충돌 문구다
    with raises_with(InvalidValueError, SYNC_CONFLICT_MESSAGE):
        finalize_sequence(LOST, steps, CATALOG)


def test_a_missing_answer_in_the_second_step_is_reported() -> None:
    """두 번째 변경에 필요한 답이 없으면 선택 필수 문구다.

    테스트 코드: AC-033
    """
    # when·then: Lost에서 Status 제품소개 뒤 답 없는 Forecast Commit은 선택 필수 문구다
    with raises_with(InvalidValueError, CHOICE_REQUIRED):
        finalize_sequence(LOST, [_status("introduction"), _forecast("commit")], CATALOG)


def test_a_missing_revenue_in_the_first_step_is_reported_first() -> None:
    """첫 변경의 매출 누락이 먼저 알려진다.

    테스트 코드: AC-024
    """
    # when·then: 매출 없는 계약완료 뒤 Forecast Best를 확정하면 매출 필수 문구다
    with raises_with(InvalidValueError, REVENUE_REQUIRED):
        finalize_sequence(START, [_status("contract_completed"), _forecast("best")], CATALOG)


def test_duplicate_fields_are_rejected() -> None:
    """같은 필드를 두 번 바꾸면 거절한다.

    테스트 코드: AC-034
    """
    # when·then: Status를 두 번 바꾸면 중복 문구다
    with raises_with(InvalidValueError, SYNC_DUPLICATE_MESSAGE):
        finalize_sequence(START, [_status("introduction"), _status("poc_completed")], CATALOG)


def test_more_than_two_steps_are_rejected() -> None:
    """변경이 세 개 이상이면 거절한다.

    테스트 코드: AC-034
    """
    # given: Status·Forecast·Status 세 변경
    steps = [_status("introduction"), _forecast("best"), _status("poc_completed")]

    # when·then: 순차 확정을 하면 중복 문구다
    with raises_with(InvalidValueError, SYNC_DUPLICATE_MESSAGE):
        finalize_sequence(START, steps, CATALOG)


def test_each_step_uses_only_its_own_resolution() -> None:
    """각 변경은 자기 답만 쓴다.

    테스트 코드: AC-031
    """
    # given: Won에서 답 없는 Forecast Commit 뒤 답이 딸린 Status 제품소개
    steps = [
        _forecast("commit"),
        _status("introduction", SyncResolution(status_key="poc_completed")),
    ]

    # when·then: 순차 확정을 하면 첫 변경의 선택 필수 문구다
    with raises_with(InvalidValueError, CHOICE_REQUIRED):
        finalize_sequence(WON, steps, CATALOG)


def test_same_value_second_step_is_a_no_op() -> None:
    """두 번째 변경이 현재 값과 같으면 아무것도 바꾸지 않는다.

    테스트 코드: AC-028
    """
    # when: Status 제품소개 뒤 Forecast를 현재 값 Pipeline으로 확정한다
    applied = finalize_sequence(START, [_status("introduction"), _forecast("pipeline")], CATALOG)

    # then: 두 번째 결과는 첫 결과와 같은 상태이고 함께 변경이 없다
    assert applied[1].state == applied[0].state == SyncState("introduction", "pipeline")
    assert applied[1].co_changed == ()


@pytest.mark.parametrize("message", [SYNC_CONFLICT_MESSAGE, SYNC_DUPLICATE_MESSAGE])
def test_error_messages_match_the_agreed_wording(message: str) -> None:
    """충돌·중복 문구는 합의한 문구다.

    테스트 코드: AC-032, AC-034
    """
    # when·then: 상수 문구를 읽으면 합의한 두 문장 중 하나다
    assert message in {
        "먼저 바꾼 값과 맞지 않는 변경입니다. 먼저 바꾼 값을 되돌린 뒤 다시 선택하세요.",
        "Status와 Forecast는 한 번에 각각 한 번만 바꿀 수 있습니다.",
    }
