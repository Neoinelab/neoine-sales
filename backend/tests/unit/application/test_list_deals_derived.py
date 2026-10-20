"""목록·상세의 파생값(AC-22·23): next_action(최근 Action의 다음 진행 계획)과 last_updated_at.

last_updated_at은 가장 최근 Action 수행 시각(없으면 Deal 등록 시각, E4)이고 기본 정렬 기준이다.
"""

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from app.domain.deal_action.next_action_status import NextActionStatus

from app.application.ports.deal_repository import DealQuery, NextActionSummary
from tests.factories import NOW, make_deal_action
from tests.factories_deal import SALES, make_patch
from tests.support.user_ids import ACTOR_ID

if TYPE_CHECKING:
    from app.application.deal.dto import DealView
    from tests.unit.application.deal_env import DealEnv


async def _act(
    env: DealEnv,
    view: DealView,
    *,
    acted_at: datetime,
    next_action: str = "견적서 전달",
    due_date: date = date(2026, 2, 1),
) -> None:
    """수행 시각을 정해 Action을 저장소에 직접 둔다(파생값 계산만 본다. 등록 규칙은 별도 테스트)."""
    await env.uow.deal_actions.add(
        make_deal_action(
            deal_code=view.item.deal.id,
            acted_at=acted_at,
            actor_user_id=ACTOR_ID,
            next_action=next_action,
            due_date=due_date,
        )
    )


async def _row(env: DealEnv, view: DealView) -> DealView:
    page = await env.list.execute(DealQuery(keyword=view.item.deal.id.value))
    return page.items[0]


async def test_a_deal_without_actions_has_no_next_action_and_its_registration_time(
    env: DealEnv,
) -> None:
    view = await env.new_deal()

    row = await _row(env, view)

    assert row.item.next_action is None
    assert row.item.last_updated_at == view.item.deal.created_at


async def test_the_latest_action_provides_the_next_action_and_the_update_time(
    env: DealEnv,
) -> None:
    view = await env.new_deal()
    acted_at = view.item.deal.updated_at + timedelta(days=3)
    await _act(env, view, acted_at=acted_at, next_action="계약서 검토", due_date=date(2026, 2, 5))

    row = await _row(env, view)

    assert row.item.next_action == NextActionSummary(
        text="계약서 검토", due_date=date(2026, 2, 5), status=NextActionStatus.OPEN
    )
    assert row.item.last_updated_at == acted_at


async def test_the_action_with_the_latest_acted_at_wins_regardless_of_registration_order(
    env: DealEnv,
) -> None:
    view = await env.new_deal()
    base = view.item.deal.updated_at
    await _act(env, view, acted_at=base + timedelta(days=5), next_action="나중 일")
    await _act(env, view, acted_at=base + timedelta(days=2), next_action="먼저 한 일")

    row = await _row(env, view)

    assert row.item.next_action is not None
    assert row.item.next_action.text == "나중 일"
    assert row.item.last_updated_at == base + timedelta(days=5)


async def test_an_action_older_than_the_deal_update_still_sets_the_update_time(
    env: DealEnv,
) -> None:
    view = await env.new_deal()
    await _act(env, view, acted_at=datetime(2025, 1, 1, tzinfo=UTC))

    row = await _row(env, view)

    assert row.item.last_updated_at == datetime(2025, 1, 1, tzinfo=UTC)
    assert row.item.next_action is not None  # 수행 시각이 오래돼도 가장 최근 Action이다


async def test_a_deal_with_a_recent_action_ranks_above_a_more_recently_edited_deal(
    env: DealEnv,
) -> None:
    older = await env.new_deal()
    newer = await env.new_deal()
    await _act(env, older, acted_at=newer.item.deal.updated_at + timedelta(days=1))

    page = await env.list.execute(DealQuery())

    assert [v.item.deal.id for v in page.items] == [older.item.deal.id, newer.item.deal.id]


async def test_the_detail_carries_the_same_derived_values(env: DealEnv) -> None:
    view = await env.new_deal()
    acted_at = NOW + timedelta(days=30)
    await _act(env, view, acted_at=acted_at, next_action="최종 협상", due_date=date(2026, 3, 1))

    detail = await env.get.execute(view.item.deal.id.value)

    assert detail.item.next_action == NextActionSummary(
        text="최종 협상", due_date=date(2026, 3, 1), status=NextActionStatus.OPEN
    )
    assert detail.item.last_updated_at == acted_at


async def test_a_deal_edit_does_not_move_the_update_time(env: DealEnv) -> None:
    view = await env.new_deal()
    created = view.item.deal.created_at
    env.clock.advance(3600)

    await env.update.execute(view.item.deal.id.value, make_patch(name="바뀐 이름"), SALES)

    assert (await _row(env, view)).item.last_updated_at == created
