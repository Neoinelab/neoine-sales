"""RegisterDealAction + 이전 Next Action 종료: 기한초과 Deal의 종료 대상은 새 기준 행(RK-R1).

이전 Next Action의 기준 행은 지난 Open 중 Due가 가장 이른 행(없으면 가장 최근 행)이다. "오늘"은
서버 시계를 Asia/Seoul 날짜로 바꾼 값이고 `_given`이 2026-01-10으로 맞춘다.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.deal.risk import Risk
from app.domain.deal_action.next_action_status import NextActionState, NextActionStatus
from app.domain.deal_action.value_objects import DealActionId
from tests.factories import make_deal_action
from tests.support.expect import raises_with
from tests.unit.application.action_env import KIM

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.domain.deal_action.entities import DealAction
    from tests.unit.application.action_env import ActionEnv

CHANGED = "이전 Next Action이 바뀌었습니다. 창을 닫고 다시 열어 주세요."
TOO_EARLY = (
    "이전 Next Action의 수행일(2026-01-02)보다 앞선 날짜로는 이전 Next Action을 종료할 수 없습니다."
)
TODAY = date(2026, 1, 10)
TODAY_UTC = datetime(2026, 1, 10, 9, 0, tzinfo=UTC)  # Seoul 2026-01-10 18:00


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def _row(
    action_env: ActionEnv, row_id: int, *, acted_on: date, text: str, due: date
) -> DealAction:
    """KIM이 남긴 Open Next Action 행을 저장소에 직접 둔다(id를 정해 둔다)."""
    action = make_deal_action(
        deal_code=action_env.deal.item.deal.id,
        now=action_env.env.clock.now(),
        actor_user_id=KIM.user_id,
        acted_on=acted_on,
        entity_id=DealActionId(row_id),
        next_action=text,
        due_date=due,
    )
    await action_env.env.uow.deal_actions.add(action)
    return action


async def _given(action_env: ActionEnv) -> tuple[DealAction, DealAction, DealAction]:
    """AC-146의 Deal: A(01-02, Due 01-05)·B(01-04, Due 01-08)·C(01-09, Due 01-20), 오늘 01-10."""
    a = await _row(
        action_env, 601, acted_on=date(2026, 1, 2), text="견적 발송", due=date(2026, 1, 5)
    )
    b = await _row(action_env, 602, acted_on=date(2026, 1, 4), text="제안서", due=date(2026, 1, 8))
    c = await _row(action_env, 603, acted_on=date(2026, 1, 9), text="데모", due=date(2026, 1, 20))
    action_env.set_clock(TODAY_UTC)
    return a, b, c


async def _state(action_env: ActionEnv, action: DealAction) -> NextActionState | None:
    return (await action_env.stored(action.id)).next_action_state


async def test_closing_the_earliest_past_open_row_is_accepted_and_saved_with_history(
    action_env: ActionEnv,
) -> None:
    """종료 대상은 지난 Open 중 Due가 가장 이른 행이고 그 행을 닫으며 등록된다.

    테스트 코드: AC-146
    """
    # given: 오늘 01-10. KIM의 Open Next Action A(Due 01-05)·B(Due 01-08)·C(Due 01-20)
    a, b, c = await _given(action_env)
    before = await action_env.rows()

    # when: A.id를 닫도록 지정해 진행사항 "견적 발송 완료"를 등록한다
    created = await action_env.act(
        KIM, advance=0, close_previous=a.id, action="견적 발송 완료", next_action=""
    )

    # then: 등록된 Action이 저장되고 A는 done(종료일 2026-01-10)이며 B·C는 Open 그대로다
    assert (await action_env.stored(created.id)).content.action == "견적 발송 완료"
    assert await _state(action_env, a) == NextActionState(NextActionStatus.DONE, closed_on=TODAY)
    assert await _state(action_env, b) == NextActionState.open()
    assert await _state(action_env, c) == NextActionState.open()
    # then: 이력은 A의 Next Action 종료 줄 다음에 등록 줄이다
    closing, registration = (await action_env.rows())[len(before) :]
    assert closing[:2] == ("action", "Next Action")
    assert "견적 발송" in closing[2]
    assert closing[3] == "종료(수행)"
    assert registration[:2] == ("action", "Action")
    assert registration[3].startswith("등록:")


async def test_the_most_recent_row_id_is_conflict_when_a_past_open_row_exists(
    action_env: ActionEnv,
) -> None:
    """기한초과 Deal에서 가장 최근 Next Action 행 id로 종료를 요청하면 409이고 저장되지 않는다.

    테스트 코드: AC-147
    """
    # given: AC-146과 같은 Deal과 등록 전 이력·커밋
    a, b, c = await _given(action_env)
    rows = await action_env.rows()
    commits = action_env.env.uow.commits

    for stale in (c, b):
        # when·then: C.id(가장 최근 행)와 B.id(두 번째 지난 Open)로 등록하면 409다
        with raises_with(InvalidStateError, CHANGED):
            await action_env.act(KIM, advance=0, close_previous=stale.id, action="진행")

    # then: Action 수·세 행의 상태·이력·커밋이 그대로다
    assert len(action_env.env.uow.deal_actions._items) == 3
    for action in (a, b, c):
        assert await _state(action_env, action) == NextActionState.open()
    assert await action_env.rows() == rows
    assert action_env.env.uow.commits == commits


async def test_the_acted_on_check_uses_the_acted_on_of_the_new_basis_row(
    action_env: ActionEnv,
) -> None:
    """종료 대상 수행일 판정은 새 기준 행(A)의 수행일로 한다. 가장 최근 행(C)의 수행일이 아니다.

    테스트 코드: AC-148
    """
    # given: A(01-02 수행, Due 01-05, Open)와 C(01-09 수행, Due 01-20, Open)만 있는 Deal이다
    a = await _row(
        action_env, 701, acted_on=date(2026, 1, 2), text="견적 발송", due=date(2026, 1, 5)
    )
    await _row(action_env, 703, acted_on=date(2026, 1, 9), text="데모", due=date(2026, 1, 20))
    action_env.set_clock(TODAY_UTC)
    count = len(action_env.env.uow.deal_actions._items)

    # when·then: A.id 종료에 수행일 01-01을 주면 A의 수행일(01-02)보다 앞이라 422다
    with raises_with(InvalidValueError, TOO_EARLY):
        await action_env.act(
            KIM, advance=0, close_previous=a.id, acted_on=date(2026, 1, 1), action="진행"
        )
    # then: 아무것도 저장되지 않았다
    assert len(action_env.env.uow.deal_actions._items) == count
    assert await _state(action_env, a) == NextActionState.open()

    # when: A.id 종료에 수행일 01-03을 주고 등록한다(C의 수행일 01-09보다 앞이다)
    await action_env.act(
        KIM, advance=0, close_previous=a.id, acted_on=date(2026, 1, 3), action="진행"
    )

    # then: 등록되고 A가 done이다
    state = await _state(action_env, a)
    assert state is not None
    assert state.status is NextActionStatus.DONE


async def test_after_closing_past_open_rows_the_next_action_falls_back_in_order(
    action_env: ActionEnv,
) -> None:
    """지난 Open 행을 닫은 뒤 next_action은 남은 지난 Open 행, 그것도 없으면 가장 최근 행이다.

    테스트 코드: AC-149
    """
    # given: AC-146과 같은 Deal
    a, b, _ = await _given(action_env)
    code = action_env.code

    # when: A.id를 닫으며 진행사항만 있는 Action D를 등록하고 상세를 조회한다
    await action_env.act(KIM, advance=0, close_previous=a.id, action="진행 D", next_action="")
    first = await action_env.env.get.execute(code)

    # then: next_action은 B(Due 01-08, open, action_id B)이고 기한초과가 있다
    assert first.item.next_action is not None
    assert first.item.next_action.due_date == date(2026, 1, 8)
    assert first.item.next_action.status is NextActionStatus.OPEN
    assert first.item.next_action.action_id == b.id
    assert first.risk in (Risk.OVERDUE, Risk.OVERDUE_STALE)

    # when: B.id를 닫으며 Next Action "계약 검토"(Due 01-25)인 Action E를 등록하고 다시 조회한다
    created = await action_env.act(
        KIM, advance=0, close_previous=b.id, next_action="계약 검토", due_date=date(2026, 1, 25)
    )
    second = await action_env.env.get.execute(code)

    # then: next_action은 E이고 기한초과가 아니다
    assert second.item.next_action is not None
    assert second.item.next_action.text == "계약 검토"
    assert second.item.next_action.action_id == created.id
    assert second.risk not in (Risk.OVERDUE, Risk.OVERDUE_STALE)
