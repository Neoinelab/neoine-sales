"""RegisterDealAction + 두 변경: 순서대로 적용, 부분 저장 없음."""

from datetime import date
from typing import TYPE_CHECKING

from app.application.deal_action.inputs import StatusChangeInput
from app.domain.common.errors import InvalidValueError
from app.domain.deal.sync import SYNC_CONFLICT_MESSAGE, SyncResolution, SyncState
from tests.support.expect import raises_with
from tests.unit.application.action_env import ACTION_OR_NEXT_REQUIRED, SUMMARY
from tests.unit.application.apply_helpers import CHOICE_REQUIRED, CLOSING

if TYPE_CHECKING:
    from app.domain.deal.entities import Deal
    from tests.unit.application.action_env import ActionEnv

UNKNOWN_CODE = "존재하지 않는 코드입니다."
ACTION_ROW = ("action", "Action", "", f"등록: {SUMMARY} / Memo: 요구사항 정리")


def _status(value: str, resolution: SyncResolution | None = None) -> StatusChangeInput:
    return StatusChangeInput(field="status_key", value=value, resolution=resolution)


def _forecast(value: str, resolution: SyncResolution | None = None) -> StatusChangeInput:
    return StatusChangeInput(field="forecast_key", value=value, resolution=resolution)


async def _deal(action_env: ActionEnv, code: str | None = None) -> Deal:
    from app.domain.deal.code import DealCode  # noqa: PLC0415

    return await action_env.env.uow.deals.get(DealCode(code or action_env.code))


async def _won_code(action_env: ActionEnv) -> str:
    won = await action_env.env.new_deal(
        status_key="contract_completed",
        forecast_key="won",
        revenue_amount=777,
        revenue_date=date(2026, 9, 1),
    )
    return won.item.deal.id.value


async def _lost_code(action_env: ActionEnv) -> str:
    lost = await action_env.env.new_deal(status_key="prospecting", forecast_key="lost")
    return lost.item.deal.id.value


async def test_two_changes_are_saved_with_the_action_in_order(action_env: ActionEnv) -> None:
    """Status와 Forecast 두 변경을 순서대로 적용하고 이력도 그 순서다.

    테스트 코드: AC-030
    """
    # when: Status 제품소개, Forecast Best 순서로 바꾸며 등록한다
    action = await action_env.act(status_changes=(_status("introduction"), _forecast("best")))

    # then: Deal과 스냅숏이 제품소개·Best이고 수정 시각은 수행 시각이다
    deal = await _deal(action_env)
    assert (deal.sync.status_key, deal.sync.forecast_key) == ("introduction", "best")
    assert (await action_env.stored(action.id)).snapshot == SyncState("introduction", "best")
    assert deal.updated_at == action.acted_at
    # then: 이력은 Status, Forecast, Action 등록 순서다
    assert await action_env.rows() == [
        ("status", "Status", "기회발굴", "제품소개"),
        ("forecast", "Forecast", "Pipeline", "Best"),
        ACTION_ROW,
    ]


async def test_reopen_then_status_change_records_each_change(action_env: ActionEnv) -> None:
    """두 번째 변경은 첫 변경을 적용한 상태로 판정한다.

    테스트 코드: AC-031
    """
    # given: 계약완료·Won인 Deal
    code = await _won_code(action_env)
    steps = (
        _forecast("commit", SyncResolution(status_key="poc_completed")),
        _status("introduction"),
    )

    # when: Forecast Commit(답 PoC완료)에 이어 Status 제품소개로 바꾸며 등록한다
    action = await action_env.act(code=code, status_changes=steps)

    # then: Deal과 스냅숏은 제품소개·Commit이다
    deal = await _deal(action_env, code)
    assert (deal.sync.status_key, deal.sync.forecast_key) == ("introduction", "commit")
    assert (await action_env.stored(action.id)).snapshot == SyncState("introduction", "commit")
    # then: 단계마다 이력이 남는다
    rows = await action_env.rows(code)
    assert [r[0] for r in rows] == ["status", "forecast", "status", "action"]
    assert "Forecast Commit과 함께 변경" in rows[0][3]
    assert rows[1][3] == "Commit"
    assert rows[2][3] == "제품소개"


async def test_a_conflicting_second_change_stores_nothing(action_env: ActionEnv) -> None:
    """두 번째 변경이 첫 변경 값을 뒤집으면 아무것도 저장되지 않는다.

    테스트 코드: AC-032
    """
    # given: 등록 전 Deal과 커밋 횟수
    before = await _deal(action_env)
    commits = action_env.env.uow.commits

    # when·then: Status 제품소개 뒤 Forecast Won을 고르면 충돌 오류다
    with raises_with(InvalidValueError, SYNC_CONFLICT_MESSAGE):
        await action_env.act(status_changes=(_status("introduction"), _forecast("won", CLOSING)))

    # then: Deal·Action·이력·커밋 횟수가 그대로다
    after = await _deal(action_env)
    assert (after.sync, after.updated_at) == (before.sync, before.updated_at)
    assert len(action_env.env.uow.deal_actions._items) == 0
    assert await action_env.rows() == []
    assert action_env.env.uow.commits == commits


async def test_a_failing_second_change_does_not_keep_the_first(action_env: ActionEnv) -> None:
    """두 번째 변경이 실패하면 첫 변경도 저장되지 않는다.

    테스트 코드: AC-033
    """
    # given: Forecast가 Lost인 Deal
    code = await _lost_code(action_env)

    # when·then: Status 제품소개 뒤 답 없는 Forecast Commit은 선택 필수 오류다
    with raises_with(InvalidValueError, CHOICE_REQUIRED):
        await action_env.act(
            code=code, status_changes=(_status("introduction"), _forecast("commit"))
        )

    # then: Deal은 그대로이고 이력·Action이 없다
    deal = await _deal(action_env, code)
    assert (deal.sync.status_key, deal.sync.forecast_key) == ("prospecting", "lost")
    assert await action_env.rows(code) == []
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_an_unknown_code_in_the_second_change_is_rejected(action_env: ActionEnv) -> None:
    """두 번째 항목의 없는 코드는 거절된다.

    테스트 코드: AC-027
    """
    # when·then: 유효한 Status 변경 뒤 없는 Forecast 코드를 주면 코드 없음 오류다
    with raises_with(InvalidValueError, UNKNOWN_CODE):
        await action_env.act(status_changes=(_status("introduction"), _forecast("no_such")))

    # then: Deal·이력·Action이 그대로다
    assert (await _deal(action_env)).sync == SyncState("prospecting", "pipeline")
    assert await action_env.rows() == []
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_invalid_content_is_reported_before_any_change(action_env: ActionEnv) -> None:
    """내용 오류는 두 변경보다 먼저 판정된다.

    테스트 코드: AC-029
    """
    # when·then: 내용이 빈 등록에 두 변경을 실으면 내용 오류다
    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        await action_env.act(
            action="  ",
            next_action="",
            due_date=None,
            status_changes=(_status("introduction"), _forecast("best")),
        )

    # then: Deal은 그대로이고 이력이 없다
    assert (await _deal(action_env)).sync == SyncState("prospecting", "pipeline")
    assert await action_env.rows() == []


async def test_status_changed_at_moves_when_either_change_moves_the_status(
    action_env: ActionEnv,
) -> None:
    """두 변경 중 하나라도 Status를 옮기면 Status 진입 시각이 수행 시각이다."""
    # when: Forecast 변경에 이어 Status 변경을 함께 등록한다
    action = await action_env.act(status_changes=(_forecast("best"), _status("introduction")))

    # then: Status 진입 시각이 수행 시각이고 진입 Status가 바뀐다
    deal = await _deal(action_env)
    assert deal.status_changed_at == action.acted_at
    assert deal.status_entry.status_key == "introduction"


async def test_two_same_value_changes_leave_the_deal_untouched(action_env: ActionEnv) -> None:
    """두 변경이 모두 현재 값이면 Deal은 그대로이고 Action만 남는다.

    테스트 코드: AC-028
    """
    # given: 등록 전 Deal
    before = await _deal(action_env)

    # when: 현재 Status·Forecast와 같은 값으로 바꾸며 등록한다
    action = await action_env.act(status_changes=(_status("prospecting"), _forecast("pipeline")))

    # then: Deal·수정 시각이 그대로이고 스냅숏은 현재 값이다
    after = await _deal(action_env)
    assert (after.sync, after.updated_at) == (before.sync, before.updated_at)
    assert (await action_env.stored(action.id)).snapshot == SyncState("prospecting", "pipeline")
    # then: 이력은 Action 등록 1건뿐이다
    assert await action_env.rows() == [ACTION_ROW]


async def test_an_unknown_code_is_reported_before_the_revenue_check_of_the_first_change(
    action_env: ActionEnv,
) -> None:
    """두 번째 항목의 없는 코드는 첫 항목의 매출 판정보다 먼저 본다.

    테스트 코드: AC-027
    """
    # when·then: 답 없는 계약완료 뒤 없는 Forecast 코드를 주면 코드 없음 오류다
    with raises_with(InvalidValueError, UNKNOWN_CODE):
        await action_env.act(status_changes=(_status("contract_completed"), _forecast("nope")))

    # then: Deal·이력·Action이 그대로다
    assert (await _deal(action_env)).sync == SyncState("prospecting", "pipeline")
    assert await action_env.rows() == []
    assert len(action_env.env.uow.deal_actions._items) == 0
