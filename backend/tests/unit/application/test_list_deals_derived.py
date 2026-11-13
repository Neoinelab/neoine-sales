"""목록·상세의 파생값: next_action(최근 Action의 다음 진행 계획)과 last_updated_on.

last_updated_on은 가장 최근 Action 수행일(없으면 Deal 등록일, 날짜만, RK-R2)이고 기본 정렬 기준이다.
"""

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery, NextActionSummary
from app.domain.deal_action.next_action_status import NextActionStatus
from tests.factories import make_deal_action
from tests.factories_deal import SALES, make_patch
from tests.support.user_ids import ACTOR_ID

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.deal.dto import DealView
    from tests.unit.application.deal_env import DealEnv


async def _act(
    env: DealEnv,
    view: DealView,
    *,
    acted_on: date,
    next_action: str = "견적서 전달",
    due_date: date = date(2026, 2, 1),
) -> None:
    """수행일을 정해 Action을 저장소에 직접 둔다(파생값 계산만 본다. 등록 규칙은 별도 테스트)."""
    await env.uow.deal_actions.add(
        make_deal_action(
            now=env.clock.now(),
            deal_code=view.item.deal.id,
            acted_on=acted_on,
            actor_user_id=ACTOR_ID,
            next_action=next_action,
            due_date=due_date,
        )
    )


def _registered_on(view: DealView) -> date:
    """Deal 등록일(업무 날짜)."""
    return view.item.deal.created_at.astimezone().date()


async def _row(env: DealEnv, view: DealView) -> DealView:
    page = await env.list.execute(DealQuery(keyword=view.item.deal.id.value))
    return page.items[0]


async def test_a_deal_without_actions_has_no_next_action_and_its_registration_date(
    env: DealEnv,
) -> None:
    """Action이 없으면 next_action은 없고 최종 업데이트일은 등록일이다.

    테스트 코드: RK-003, RK-005
    """
    # given: Action이 없는 Deal이다
    view = await env.new_deal()

    # when: 목록을 조회한다
    row = await _row(env, view)

    # then: next_action이 없고 last_updated_on이 등록일(date)이다
    assert row.item.next_action is None
    assert row.item.last_updated_on == _registered_on(view)


async def test_the_latest_action_provides_the_next_action_and_the_update_date(
    env: DealEnv,
) -> None:
    """가장 최근 Action이 Next Action과 최종 업데이트일을 준다.

    테스트 코드: RK-001, RK-004
    """
    # given: 등록 3일 뒤 수행한 Next Action이 있는 Deal이다
    view = await env.new_deal()
    acted_on = _registered_on(view) + timedelta(days=3)
    await _act(env, view, acted_on=acted_on, next_action="계약서 검토", due_date=date(2026, 2, 5))

    # when: 목록을 조회한다
    row = await _row(env, view)

    # then: next_action이 그 Action의 값이고 last_updated_on이 수행일이다
    assert row.item.next_action == NextActionSummary(
        text="계약서 검토", due_date=date(2026, 2, 5), status=NextActionStatus.OPEN
    )
    assert row.item.last_updated_on == acted_on


async def test_the_action_with_the_latest_acted_on_wins_regardless_of_registration_order(
    env: DealEnv,
) -> None:
    """최종 업데이트일은 등록 순서와 무관하게 가장 늦은 수행일이다.

    테스트 코드: RK-004
    """
    # given: 수행일이 등록+5일인 Action을 저장한 뒤 등록+2일인 Action을 저장했다
    view = await env.new_deal()
    base = _registered_on(view)
    await _act(env, view, acted_on=base + timedelta(days=5), next_action="나중 일")
    await _act(env, view, acted_on=base + timedelta(days=2), next_action="먼저 한 일")

    # when: 목록을 조회한다
    row = await _row(env, view)

    # then: 수행일이 가장 늦은 Action이 next_action과 last_updated_on을 정한다
    assert row.item.next_action is not None
    assert row.item.next_action.text == "나중 일"
    assert row.item.last_updated_on == base + timedelta(days=5)


async def test_an_action_older_than_the_deal_update_still_sets_the_update_time(
    env: DealEnv,
) -> None:
    """Deal 등록일보다 오래된 수행일의 Action도 최종 업데이트일을 정한다.

    테스트 코드: RK-004
    """
    # given: Deal 등록일보다 오래전 수행일(2025-01-01)의 Action이 있는 Deal이다
    view = await env.new_deal()
    await _act(env, view, acted_on=date(2025, 1, 1))

    # when: 목록을 조회한다
    row = await _row(env, view)

    # then: last_updated_on이 그 수행일이고 next_action이 있다
    assert row.item.last_updated_on == date(2025, 1, 1)
    assert row.item.next_action is not None  # 수행일이 오래돼도 가장 최근 Action이다


async def test_a_deal_with_a_recent_action_ranks_above_a_more_recently_edited_deal(
    env: DealEnv,
) -> None:
    """최근 Action이 있는 Deal이 더 최근에 등록된 Deal보다 위에 정렬된다."""
    # given: 최근 Action이 있는 Deal과 나중에 등록한 Deal이다
    older = await env.new_deal()
    newer = await env.new_deal()
    await _act(env, older, acted_on=_registered_on(newer) + timedelta(days=1))

    # when: 기본 정렬로 목록을 조회한다
    page = await env.list.execute(DealQuery())

    # then: Action이 있는 Deal이 먼저 나온다
    assert [v.item.deal.id for v in page.items] == [older.item.deal.id, newer.item.deal.id]


async def test_the_detail_carries_the_same_derived_values(env: DealEnv) -> None:
    """상세도 목록과 같은 next_action·last_updated_on을 준다.

    테스트 코드: RK-008
    """
    # given: 수행한 Next Action이 있는 Deal이다
    view = await env.new_deal()
    acted_on = _registered_on(view) + timedelta(days=30)
    await _act(env, view, acted_on=acted_on, next_action="최종 협상", due_date=date(2026, 3, 1))

    # when: 상세를 조회한다
    detail = await env.get.execute(view.item.deal.id.value)

    # then: next_action과 last_updated_on이 Action의 값이다
    assert detail.item.next_action == NextActionSummary(
        text="최종 협상", due_date=date(2026, 3, 1), status=NextActionStatus.OPEN
    )
    assert detail.item.last_updated_on == acted_on


async def test_a_deal_edit_does_not_move_the_update_time(env: DealEnv) -> None:
    """Deal 수정은 최종 업데이트일을 바꾸지 않는다.

    테스트 코드: RK-005
    """
    # given: Action이 없는 Deal이 등록되고 하루가 지났다
    view = await env.new_deal()
    created = _registered_on(view)
    env.clock.advance(86400)

    # when: 이름을 수정한 뒤 목록을 조회한다
    await env.update.execute(view.item.deal.id.value, make_patch(name="바뀐 이름"), SALES)

    # then: last_updated_on은 등록일 그대로다
    assert (await _row(env, view)).item.last_updated_on == created


async def test_a_deal_without_actions_uses_the_business_date_of_registration_not_the_utc_date(
    env: DealEnv, local_tz: Callable[[str], None]
) -> None:
    """Action이 없으면 최종 업데이트일은 업무 시간대 기준 Deal 등록일이다(UTC 날짜가 아님).

    테스트 코드: RK-067
    """
    # given: 서버 시간대 Asia/Seoul, UTC 1월 1일 16:00(서울 1월 2일 01:00)에 등록한 Action 없는 Deal
    local_tz("Asia/Seoul")
    env.clock.advance((datetime(2026, 1, 1, 16, 0, tzinfo=UTC) - env.clock.now()).total_seconds())
    view = await env.new_deal()

    # when: 목록과 상세를 조회한다
    row = await _row(env, view)
    detail = await env.get.execute(view.item.deal.id.value)

    # then: 최종 업데이트일은 서울 날짜 2026-01-02(date)다
    assert row.item.last_updated_on == date(2026, 1, 2)
    assert detail.item.last_updated_on == date(2026, 1, 2)
