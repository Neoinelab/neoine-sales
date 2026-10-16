"""RegisterDealAction(AC-01~04): 수행 일시·담당자는 서버가 채우고, 스냅숏·이력을 남긴다."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.deal.inputs import Actor
from app.application.ports.deal_repository import NextActionSummary
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.sync import SyncState
from app.domain.deal_action.value_objects import ActionType
from tests.support.expect import raises_with
from tests.support.user_ids import uid
from tests.unit.application.action_env import (
    KIM,
    PROGRESS_REQUIRED,
    SUMMARY_WITH_MEMO,
)

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv


async def test_register_action_sets_now_requester_and_current_snapshot(
    action_env: ActionEnv,
) -> None:
    deal = await action_env.env.new_deal(status_key="introduction", forecast_key="best")
    action_env.env.clock.advance(300)

    action = await action_env.act(KIM, code=deal.item.deal.id.value, memo="요구사항 정리")

    stored = await action_env.stored(action.id)
    assert stored.acted_at == action_env.env.clock.now()
    assert stored.created_at == stored.updated_at == stored.acted_at
    assert stored.actor_user_id == KIM.user_id
    assert stored.snapshot == SyncState("introduction", "best")
    assert stored.deal_code == deal.item.deal.id
    assert stored.content.action_type is ActionType.MEETING
    assert stored.content.next_action == "요구사항 문서 전달"
    assert stored.content.due_date == date(2026, 1, 15)


async def test_register_action_trims_every_text_and_keeps_a_past_due_date(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(
        action="  킥오프  ", next_action=" 견적 ", memo="  메모  ", due_date=date(2000, 1, 1)
    )

    content = (await action_env.stored(action.id)).content
    assert (content.action, content.next_action, content.memo) == ("킥오프", "견적", "메모")
    assert content.due_date == date(2000, 1, 1)


async def test_register_action_saves_long_text_in_full(action_env: ActionEnv) -> None:
    action = await action_env.act(action="가" * 5_000, next_action="😀" * 5_000, memo="메" * 20_000)

    content = (await action_env.stored(action.id)).content
    assert len(content.action) == 5_000
    assert len(content.next_action) == 5_000
    assert len(content.memo) == 20_000


@pytest.mark.parametrize("code", ["20261016-ZZZZ", "not-a-code"])
async def test_register_action_on_missing_or_malformed_deal_is_not_found_before_validation(
    action_env: ActionEnv, code: str
) -> None:
    with raises_with(DealNotFoundError, "Deal을 찾을 수 없습니다."):
        await action_env.act(code=code, action="  ", next_action="", due_date=None)


async def test_register_action_with_blank_progress_stores_nothing(action_env: ActionEnv) -> None:
    commits = action_env.env.uow.commits

    with raises_with(InvalidValueError, PROGRESS_REQUIRED):
        await action_env.act(action="   ")

    assert action_env.env.uow.commits == commits
    assert await action_env.rows() == []
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_register_action_without_due_date_is_rejected(action_env: ActionEnv) -> None:
    with raises_with(InvalidValueError, "Due Date를 입력하세요."):
        await action_env.act(due_date=None)

    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_register_action_records_one_action_history_and_keeps_deal_updated_at(
    action_env: ActionEnv,
) -> None:
    before = (await action_env.env.uow.deals.get(action_env.deal.item.deal.id)).updated_at

    action = await action_env.act(KIM)

    assert await action_env.rows() == [
        ("action", "Action", "", f"등록: {SUMMARY_WITH_MEMO}"),
    ]
    entry = (await action_env.action_entries())[0]
    assert entry.changed_by == KIM.user_id
    assert entry.changed_at == action.acted_at
    deal = await action_env.env.uow.deals.get(action_env.deal.item.deal.id)
    assert deal.updated_at == before


async def test_register_action_without_memo_leaves_the_memo_out_of_the_history(
    action_env: ActionEnv,
) -> None:
    await action_env.act(memo="")

    (row,) = await action_env.rows()
    assert row[3] == "등록: 미팅 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2026-01-15)"


async def test_register_action_clips_the_history_but_not_the_action(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(action="가" * 2_000)

    (row,) = await action_env.rows()
    assert len(row[3]) == 1_000
    assert row[3].endswith("…")
    assert len((await action_env.stored(action.id)).content.action) == 2_000


async def test_the_registered_action_becomes_the_next_action_and_last_update_of_the_deal(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(next_action="계약서 검토", due_date=date(2026, 2, 5))

    detail = await action_env.env.get.execute(action_env.code)

    assert detail.item.next_action == NextActionSummary(
        text="계약서 검토", due_date=date(2026, 2, 5)
    )
    assert detail.item.last_updated_at == action.acted_at


async def test_register_action_does_not_need_a_registered_requester_user_row(
    action_env: ActionEnv,
) -> None:
    """요청자는 로그인한 사용자 그 자체이므로 별도의 자격 검사(ensure_assignable)가 없다."""
    stranger = Actor(user_id=uid("stranger"), role=Role.SALES)

    action = await action_env.act(stranger)

    assert (await action_env.stored(action.id)).actor_user_id == stranger.user_id
