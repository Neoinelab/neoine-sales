"""RegisterDealAction + 두 변경(AC-01~03·06·09·10): 순서대로 적용, 부분 저장 없음."""

from datetime import date
from typing import TYPE_CHECKING

from app.application.deal_action.inputs import StatusChangeInput
from app.domain.common.errors import InvalidValueError
from app.domain.deal.sync import SYNC_CONFLICT_MESSAGE, SyncResolution, SyncState
from tests.support.expect import raises_with
from tests.unit.application.action_env import PROGRESS_REQUIRED, SUMMARY
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
    action = await action_env.act(status_changes=(_status("introduction"), _forecast("best")))

    deal = await _deal(action_env)
    assert (deal.sync.status_key, deal.sync.forecast_key) == ("introduction", "best")
    assert (await action_env.stored(action.id)).snapshot == SyncState("introduction", "best")
    assert deal.updated_at == action.acted_at
    assert await action_env.rows() == [
        ("status", "Status", "기회발굴", "제품소개"),
        ("forecast", "Forecast", "Pipeline", "Best"),
        ACTION_ROW,
    ]


async def test_reopen_then_status_change_records_each_change(action_env: ActionEnv) -> None:
    code = await _won_code(action_env)
    steps = (
        _forecast("commit", SyncResolution(status_key="poc_completed")),
        _status("introduction"),
    )

    action = await action_env.act(code=code, status_changes=steps)

    deal = await _deal(action_env, code)
    assert (deal.sync.status_key, deal.sync.forecast_key) == ("introduction", "commit")
    assert (await action_env.stored(action.id)).snapshot == SyncState("introduction", "commit")
    rows = await action_env.rows(code)
    assert [r[0] for r in rows] == ["status", "forecast", "status", "action"]
    assert "Forecast Commit과 함께 변경" in rows[0][3]
    assert rows[1][3] == "Commit"
    assert rows[2][3] == "제품소개"


async def test_a_conflicting_second_change_stores_nothing(action_env: ActionEnv) -> None:
    before = await _deal(action_env)
    commits = action_env.env.uow.commits

    with raises_with(InvalidValueError, SYNC_CONFLICT_MESSAGE):
        await action_env.act(status_changes=(_status("introduction"), _forecast("won", CLOSING)))

    after = await _deal(action_env)
    assert (after.sync, after.updated_at) == (before.sync, before.updated_at)
    assert len(action_env.env.uow.deal_actions._items) == 0
    assert await action_env.rows() == []
    assert action_env.env.uow.commits == commits


async def test_a_failing_second_change_does_not_keep_the_first(action_env: ActionEnv) -> None:
    code = await _lost_code(action_env)

    with raises_with(InvalidValueError, CHOICE_REQUIRED):
        await action_env.act(
            code=code, status_changes=(_status("introduction"), _forecast("commit"))
        )

    deal = await _deal(action_env, code)
    assert (deal.sync.status_key, deal.sync.forecast_key) == ("prospecting", "lost")
    assert await action_env.rows(code) == []
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_an_unknown_code_in_the_second_change_is_rejected(action_env: ActionEnv) -> None:
    with raises_with(InvalidValueError, UNKNOWN_CODE):
        await action_env.act(status_changes=(_status("introduction"), _forecast("no_such")))

    assert (await _deal(action_env)).sync == SyncState("prospecting", "pipeline")
    assert await action_env.rows() == []
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_invalid_content_is_reported_before_any_change(action_env: ActionEnv) -> None:
    with raises_with(InvalidValueError, PROGRESS_REQUIRED):
        await action_env.act(
            action="  ", status_changes=(_status("introduction"), _forecast("best"))
        )

    assert (await _deal(action_env)).sync == SyncState("prospecting", "pipeline")
    assert await action_env.rows() == []


async def test_status_changed_at_moves_when_either_change_moves_the_status(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(status_changes=(_forecast("best"), _status("introduction")))

    deal = await _deal(action_env)
    assert deal.status_changed_at == action.acted_at
    assert deal.status_entry.status_key == "introduction"


async def test_two_same_value_changes_leave_the_deal_untouched(action_env: ActionEnv) -> None:
    before = await _deal(action_env)

    action = await action_env.act(status_changes=(_status("prospecting"), _forecast("pipeline")))

    after = await _deal(action_env)
    assert (after.sync, after.updated_at) == (before.sync, before.updated_at)
    assert (await action_env.stored(action.id)).snapshot == SyncState("prospecting", "pipeline")
    assert await action_env.rows() == [ACTION_ROW]
