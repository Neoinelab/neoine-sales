"""RegisterDealAction + Status/Forecast 동시 변경(AC-05~09): P1 동기화 규칙을 한 트랜잭션으로."""

from datetime import date
from typing import TYPE_CHECKING

from app.application.deal_action.inputs import StatusChangeInput
from app.domain.common.errors import InvalidValueError
from app.domain.deal.sync import SyncResolution, SyncState
from tests.support.expect import raises_with
from tests.unit.application.action_env import KIM, PROGRESS_REQUIRED, SUMMARY
from tests.unit.application.apply_helpers import (
    CHOICE_REQUIRED,
    CLOSING,
    DAY,
    REVENUE_REQUIRED,
    apply_change,
)

if TYPE_CHECKING:
    from app.domain.deal.entities import Deal
    from tests.unit.application.action_env import ActionEnv

UNKNOWN_CODE = "존재하지 않는 코드입니다."
ACTION_ROW = ("action", "Action", "", f"등록: {SUMMARY} / Memo: 요구사항 정리")


def _status(value: str, resolution: SyncResolution | None = None) -> StatusChangeInput:
    return StatusChangeInput(field="status_key", value=value, resolution=resolution)


def _forecast(value: str, resolution: SyncResolution | None = None) -> StatusChangeInput:
    return StatusChangeInput(field="forecast_key", value=value, resolution=resolution)


async def _deal(action_env: ActionEnv) -> Deal:
    return await action_env.env.uow.deals.get(action_env.deal.item.deal.id)


async def test_register_action_with_status_change_to_contract_completed_requires_revenue(
    action_env: ActionEnv,
) -> None:
    with raises_with(InvalidValueError, REVENUE_REQUIRED):
        await action_env.act(status_change=_status("contract_completed"))

    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_register_action_with_status_change_saves_post_change_snapshot_and_orders_history(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(status_change=_status("contract_completed", CLOSING))

    deal = await _deal(action_env)
    assert (deal.sync.status_key, deal.sync.forecast_key) == ("contract_completed", "won")
    assert (deal.details.revenue_amount.value, deal.details.revenue_date) == (900_000_000, DAY)
    assert deal.updated_at == action.acted_at
    assert (await action_env.stored(action.id)).snapshot == SyncState("contract_completed", "won")
    assert await action_env.rows() == [
        ("status", "Status", "기회발굴", "계약완료"),
        ("forecast", "Forecast", "Pipeline", "Won (Status 계약완료와 함께 변경)"),
        ("amount", "금액(단위:천원)", "150,000", "900,000"),
        ("expectedClose", "Expected Close", "2026-06-30", "2026-10-20"),
        ACTION_ROW,
    ]


async def test_the_action_history_is_the_newest_entry_after_a_combined_registration(
    action_env: ActionEnv,
) -> None:
    await action_env.act(status_change=_status("contract_completed", CLOSING))

    newest_first = await action_env.env.uow.deal_history.list(action_env.deal.item.deal.id)

    assert str(newest_first[0].draft.category) == "action"
    assert {e.changed_by for e in newest_first if str(e.draft.category) != "created"} == {
        KIM.user_id
    }


async def test_register_action_with_forecast_change_applies_sync_rules(
    action_env: ActionEnv,
) -> None:
    won = await action_env.act(status_change=_forecast("won", CLOSING))

    deal = await _deal(action_env)
    assert (deal.sync.status_key, deal.sync.forecast_key) == ("contract_completed", "won")
    assert (await action_env.stored(won.id)).snapshot == SyncState("contract_completed", "won")
    assert (await action_env.rows())[0] == (
        "status",
        "Status",
        "기회발굴",
        "계약완료 (Forecast Won과 함께 변경)",
    )


async def test_register_action_with_a_plain_forecast_change_keeps_the_status(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(status_change=_forecast("lost"))

    assert (await action_env.stored(action.id)).snapshot == SyncState("prospecting", "lost")
    assert await action_env.rows() == [("forecast", "Forecast", "Pipeline", "Lost"), ACTION_ROW]


async def test_register_action_status_change_reopen_won_requires_choice(
    action_env: ActionEnv,
) -> None:
    won = await action_env.env.new_deal(
        status_key="contract_completed",
        forecast_key="won",
        revenue_amount=777,
        revenue_date=date(2026, 9, 1),
    )
    code = won.item.deal.id.value

    with raises_with(InvalidValueError, CHOICE_REQUIRED):
        await action_env.act(code=code, status_change=_forecast("commit"))

    stored = await action_env.env.uow.deals.get(won.item.deal.id)
    assert (stored.sync.status_key, stored.sync.forecast_key) == ("contract_completed", "won")
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_register_action_status_change_reopen_with_a_chosen_status_snapshots_it(
    action_env: ActionEnv,
) -> None:
    won = await action_env.env.new_deal(
        status_key="contract_completed",
        forecast_key="won",
        revenue_amount=777,
        revenue_date=date(2026, 9, 1),
    )

    action = await action_env.act(
        code=won.item.deal.id.value,
        status_change=_forecast("commit", SyncResolution(status_key="poc_completed")),
    )

    assert (await action_env.stored(action.id)).snapshot == SyncState("poc_completed", "commit")


async def test_register_action_unknown_code_is_rejected(action_env: ActionEnv) -> None:
    with raises_with(InvalidValueError, UNKNOWN_CODE):
        await action_env.act(status_change=_status("no_such_status"))
    with raises_with(InvalidValueError, UNKNOWN_CODE):
        await action_env.act(status_change=_forecast("no_such_forecast"))

    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_register_action_with_failed_status_change_stores_nothing(
    action_env: ActionEnv,
) -> None:
    before = await _deal(action_env)
    commits = action_env.env.uow.commits

    with raises_with(InvalidValueError, REVENUE_REQUIRED):
        await action_env.act(status_change=_status("contract_completed"))

    after = await _deal(action_env)
    assert (after.sync, after.updated_at) == (before.sync, before.updated_at)
    assert len(action_env.env.uow.deal_actions._items) == 0
    assert await action_env.rows() == []
    assert action_env.env.uow.commits == commits


async def test_invalid_content_is_reported_before_the_status_change_is_applied(
    action_env: ActionEnv,
) -> None:
    with raises_with(InvalidValueError, PROGRESS_REQUIRED):
        await action_env.act(action="  ", status_change=_status("contract_completed"))

    deal = await _deal(action_env)
    assert deal.sync == SyncState("prospecting", "pipeline")
    assert await action_env.rows() == []


async def test_register_action_with_same_status_does_not_change_deal(
    action_env: ActionEnv,
) -> None:
    before = await _deal(action_env)

    action = await action_env.act(status_change=_status("prospecting"))

    after = await _deal(action_env)
    assert (after.sync, after.updated_at) == (before.sync, before.updated_at)
    assert (await action_env.stored(action.id)).snapshot == SyncState("prospecting", "pipeline")
    assert await action_env.rows() == [ACTION_ROW]


async def test_later_deal_change_keeps_action_snapshot(action_env: ActionEnv) -> None:
    action = await action_env.act()

    await apply_change(action_env.env, action_env.deal, "status_key", "introduction")
    await apply_change(action_env.env, action_env.deal, "forecast_key", "best")

    assert (await _deal(action_env)).sync == SyncState("introduction", "best")
    assert (await action_env.stored(action.id)).snapshot == SyncState("prospecting", "pipeline")


async def test_updating_an_action_does_not_change_its_snapshot_or_the_deal(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(status_change=_forecast("best"))
    deal_before = await _deal(action_env)

    await action_env.update_as(action.id, KIM, action="수정한 내용")

    stored = await action_env.stored(action.id)
    assert stored.snapshot == SyncState("prospecting", "best")
    assert (await _deal(action_env)).updated_at == deal_before.updated_at
