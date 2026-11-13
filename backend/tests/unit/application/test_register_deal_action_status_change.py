"""RegisterDealAction + Status/Forecast 동시 변경: 동기화 규칙을 한 트랜잭션으로."""

from datetime import date
from typing import TYPE_CHECKING

from app.application.deal_action.inputs import StatusChangeInput
from app.domain.common.errors import InvalidValueError
from app.domain.deal.sync import SyncResolution, SyncState
from tests.support.expect import raises_with
from tests.unit.application.action_env import ACTION_OR_NEXT_REQUIRED, KIM, SUMMARY
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
    """매출 없이 계약완료로 바꾸며 등록하면 거절되고 Action이 없다.

    테스트 코드: AC-024
    """
    # when·then: 매출 답 없이 계약완료로 바꾸며 등록하면 매출 필수 오류다
    with raises_with(InvalidValueError, REVENUE_REQUIRED):
        await action_env.act(status_changes=(_status("contract_completed"),))

    # then: 저장된 Action이 없다
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_register_action_with_status_change_saves_post_change_snapshot_and_orders_history(
    action_env: ActionEnv,
) -> None:
    """계약완료로 바꾸며 등록하면 변경 뒤 스냅숏과 Deal 변경 다음 등록 순서의 이력이 남는다.

    테스트 코드: AC-023
    """
    # when: 매출 답과 함께 Status를 계약완료로 바꾸며 등록한다
    action = await action_env.act(status_changes=(_status("contract_completed", CLOSING),))

    # then: Deal은 계약완료·Won이고 매출·수정 시각이 바뀐다
    deal = await _deal(action_env)
    assert (deal.sync.status_key, deal.sync.forecast_key) == ("contract_completed", "won")
    assert (deal.details.revenue_amount.value, deal.details.revenue_date) == (900_000_000, DAY)
    assert deal.updated_at == action.created_at
    # then: 스냅숏은 변경 뒤 값이다
    assert (await action_env.stored(action.id)).snapshot == SyncState("contract_completed", "won")
    # then: 이력은 Deal 변경 줄들 다음에 Action 등록 줄이다
    assert await action_env.rows() == [
        ("status", "Status", "기회발굴", "계약완료"),
        ("forecast", "Forecast", "Pipeline", "Won (Status 계약완료와 함께 변경)"),
        ("amount", "금액(단위:원)", "150,000,000", "900,000,000"),
        ("expectedClose", "Expected Close", "2026-06-30", "2026-10-20"),
        ACTION_ROW,
    ]


async def test_the_action_history_is_the_newest_entry_after_a_combined_registration(
    action_env: ActionEnv,
) -> None:
    """동반 변경이 있어도 이력 맨 위는 Action 등록 줄이다.

    테스트 코드: AC-023
    """
    # when: 계약완료로 바꾸며 등록한다
    await action_env.act(status_changes=(_status("contract_completed", CLOSING),))

    # when: 이력 목록을 읽는다
    newest_first = await action_env.env.uow.deal_history.list(action_env.deal.item.deal.id)

    # then: 맨 위는 Action 등록 줄이고 변경자는 모두 요청자다
    assert str(newest_first[0].draft.category) == "action"
    assert {e.changed_by for e in newest_first if str(e.draft.category) != "created"} == {
        KIM.user_id
    }


async def test_register_action_with_forecast_change_applies_sync_rules(
    action_env: ActionEnv,
) -> None:
    """Forecast를 Won으로 바꾸면 Status도 계약완료가 되고 이력에 함께 변경이 표기된다.

    테스트 코드: AC-023
    """
    # when: 매출 답과 함께 Forecast를 Won으로 바꾸며 등록한다
    won = await action_env.act(status_changes=(_forecast("won", CLOSING),))

    # then: Deal과 스냅숏이 계약완료·Won이다
    deal = await _deal(action_env)
    assert (deal.sync.status_key, deal.sync.forecast_key) == ("contract_completed", "won")
    assert (await action_env.stored(won.id)).snapshot == SyncState("contract_completed", "won")
    # then: 첫 이력은 Status 함께 변경 표기다
    assert (await action_env.rows())[0] == (
        "status",
        "Status",
        "기회발굴",
        "계약완료 (Forecast Won과 함께 변경)",
    )


async def test_register_action_with_a_plain_forecast_change_keeps_the_status(
    action_env: ActionEnv,
) -> None:
    """Forecast만 바꾸면 Status는 그대로이고 이력은 Forecast 다음 등록이다.

    테스트 코드: AC-025
    """
    # when: Forecast를 Lost로 바꾸며 등록한다
    action = await action_env.act(status_changes=(_forecast("lost"),))

    # then: 스냅숏은 기회발굴·Lost이고 이력은 Forecast 변경 다음 Action 등록이다
    assert (await action_env.stored(action.id)).snapshot == SyncState("prospecting", "lost")
    assert await action_env.rows() == [("forecast", "Forecast", "Pipeline", "Lost"), ACTION_ROW]


async def test_register_action_status_change_reopen_won_requires_choice(
    action_env: ActionEnv,
) -> None:
    """종결 Deal을 되돌리며 함께 바꿀 값을 고르지 않으면 거절된다.

    테스트 코드: AC-026
    """
    # given: 계약완료·Won인 Deal
    won = await action_env.env.new_deal(
        status_key="contract_completed",
        forecast_key="won",
        revenue_amount=777,
        revenue_date=date(2026, 9, 1),
    )
    code = won.item.deal.id.value

    # when·then: 답 없이 Forecast를 Commit으로 바꾸며 등록하면 선택 필수 오류다
    with raises_with(InvalidValueError, CHOICE_REQUIRED):
        await action_env.act(code=code, status_changes=(_forecast("commit"),))

    # then: Deal은 그대로이고 Action이 없다
    stored = await action_env.env.uow.deals.get(won.item.deal.id)
    assert (stored.sync.status_key, stored.sync.forecast_key) == ("contract_completed", "won")
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_register_action_status_change_reopen_with_a_chosen_status_snapshots_it(
    action_env: ActionEnv,
) -> None:
    """종결 Deal을 되돌리며 Status를 고르면 그 값이 스냅숏이 된다.

    테스트 코드: AC-026
    """
    # given: 계약완료·Won인 Deal
    won = await action_env.env.new_deal(
        status_key="contract_completed",
        forecast_key="won",
        revenue_amount=777,
        revenue_date=date(2026, 9, 1),
    )

    # when: Forecast Commit과 Status PoC완료 답으로 등록한다
    action = await action_env.act(
        code=won.item.deal.id.value,
        status_changes=(_forecast("commit", SyncResolution(status_key="poc_completed")),),
    )

    # then: 스냅숏은 PoC완료·Commit이다
    assert (await action_env.stored(action.id)).snapshot == SyncState("poc_completed", "commit")


async def test_register_action_unknown_code_is_rejected(action_env: ActionEnv) -> None:
    """없는 코드로 바꾸려 하면 거절되고 Action이 없다.

    테스트 코드: AC-027
    """
    # when·then: 없는 Status 코드로 등록하면 거절된다
    with raises_with(InvalidValueError, UNKNOWN_CODE):
        await action_env.act(status_changes=(_status("no_such_status"),))
    # when·then: 없는 Forecast 코드로 등록해도 거절된다
    with raises_with(InvalidValueError, UNKNOWN_CODE):
        await action_env.act(status_changes=(_forecast("no_such_forecast"),))

    # then: 저장된 Action이 없다
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_register_action_with_failed_status_change_stores_nothing(
    action_env: ActionEnv,
) -> None:
    """동반 변경이 실패하면 Deal·이력·Action 모두 그대로다.

    테스트 코드: AC-024
    """
    # given: 등록 전 Deal과 커밋 횟수
    before = await _deal(action_env)
    commits = action_env.env.uow.commits

    # when·then: 매출 없이 계약완료로 바꾸며 등록하면 거절된다
    with raises_with(InvalidValueError, REVENUE_REQUIRED):
        await action_env.act(status_changes=(_status("contract_completed"),))

    # then: Deal·Action·이력·커밋 횟수가 그대로다
    after = await _deal(action_env)
    assert (after.sync, after.updated_at) == (before.sync, before.updated_at)
    assert len(action_env.env.uow.deal_actions._items) == 0
    assert await action_env.rows() == []
    assert action_env.env.uow.commits == commits


async def test_invalid_content_is_reported_before_the_status_change_is_applied(
    action_env: ActionEnv,
) -> None:
    """내용 오류는 동반 변경보다 먼저 판정되어 Deal이 바뀌지 않는다.

    테스트 코드: AC-029
    """
    # when·then: 내용이 빈 등록에 계약완료 변경을 실으면 내용 오류다
    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        await action_env.act(
            action="  ",
            next_action="",
            due_date=None,
            status_changes=(_status("contract_completed"),),
        )

    # then: Deal은 그대로이고 이력이 없다
    deal = await _deal(action_env)
    assert deal.sync == SyncState("prospecting", "pipeline")
    assert await action_env.rows() == []


async def test_register_action_with_same_status_does_not_change_deal(
    action_env: ActionEnv,
) -> None:
    """현재와 같은 값으로 바꾸면 Deal은 그대로이고 Action만 남는다.

    테스트 코드: AC-028
    """
    # given: 등록 전 Deal
    before = await _deal(action_env)

    # when: 현재 Status와 같은 값으로 바꾸며 등록한다
    action = await action_env.act(status_changes=(_status("prospecting"),))

    # then: Deal·수정 시각은 그대로이고 스냅숏은 현재 값이다
    after = await _deal(action_env)
    assert (after.sync, after.updated_at) == (before.sync, before.updated_at)
    assert (await action_env.stored(action.id)).snapshot == SyncState("prospecting", "pipeline")
    # then: 이력은 Action 등록 1건뿐이다
    assert await action_env.rows() == [ACTION_ROW]


async def test_later_deal_change_keeps_action_snapshot(action_env: ActionEnv) -> None:
    """나중의 Deal 변경은 Action 스냅숏을 바꾸지 않는다.

    테스트 코드: AC-035
    """
    # given: Action을 하나 등록해 둔다
    action = await action_env.act()

    # when: Deal의 Status와 Forecast를 이어서 단일 변경한다
    await apply_change(action_env.env, action_env.deal, "status_key", "introduction")
    await apply_change(action_env.env, action_env.deal, "forecast_key", "best")

    # then: Deal은 바뀌고 Action 스냅숏은 등록 당시 값 그대로다
    assert (await _deal(action_env)).sync == SyncState("introduction", "best")
    assert (await action_env.stored(action.id)).snapshot == SyncState("prospecting", "pipeline")


async def test_updating_an_action_does_not_change_its_snapshot_or_the_deal(
    action_env: ActionEnv,
) -> None:
    """Action을 수정해도 스냅숏과 Deal은 바뀌지 않는다.

    테스트 코드: AC-035
    """
    # given: Forecast를 Best로 바꾸며 등록한 Action
    action = await action_env.act(status_changes=(_forecast("best"),))
    deal_before = await _deal(action_env)

    # when: 담당자가 진행사항을 고친다
    await action_env.update_as(action.id, KIM, action="수정한 내용")

    # then: 스냅숏은 등록 당시 값이고 Deal 수정 시각은 그대로다
    stored = await action_env.stored(action.id)
    assert stored.snapshot == SyncState("prospecting", "best")
    assert (await _deal(action_env)).updated_at == deal_before.updated_at


async def test_register_action_with_a_forecast_change_sets_the_deal_updated_at_to_the_request_time(
    action_env: ActionEnv,
) -> None:
    """Forecast만 바꾸면 Deal 수정 시각이 요청 시각이 된다.

    테스트 코드: AC-025
    """
    # when: Forecast를 Best로 바꾸며 등록한다
    action = await action_env.act(status_changes=(_forecast("best"),))

    # then: Status는 그대로이고 Deal 수정 시각은 요청 시각이다
    deal = await _deal(action_env)
    assert (deal.sync.status_key, deal.sync.forecast_key) == ("prospecting", "best")
    assert deal.updated_at == action.created_at
