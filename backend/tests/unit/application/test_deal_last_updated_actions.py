"""최종 업데이트일(`last_updated_on`)과 Action 삭제·수정·Next Action 상태 변경.

Action 등록 때만 수행일(`acted_on`)이 정해지므로 삭제는 값을 되돌리고, 수정과 상태 변경은 값을
바꾸지 않는다. "오늘"은 서버 시계를 Asia/Seoul 날짜로 바꾼 값이다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery
from tests.unit.application.action_env import KIM

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.unit.application.action_env import ActionEnv

DAY = 24 * 3600


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def _last_updated(action_env: ActionEnv) -> date:
    page = await action_env.env.list.execute(DealQuery(keyword=action_env.code))
    (row,) = page.items
    return row.item.last_updated_on


async def test_deleting_the_only_action_returns_last_updated_to_the_registration_date(
    action_env: ActionEnv,
) -> None:
    """유일한 Action을 지우면 최종 업데이트일이 Deal 등록일로 돌아간다.

    테스트 코드: RK-006
    """
    # given: 등록 5일 뒤 Action 하나를 남긴 Deal이다
    created = action_env.deal.item.deal.created_at.astimezone().date()
    action = await action_env.act(advance=5 * DAY)
    assert await _last_updated(action_env) == action.acted_on

    # when: 그 Action을 삭제한 뒤 목록을 조회한다
    await action_env.delete.execute(action.id, KIM)
    last_updated = await _last_updated(action_env)

    # then: 최종 업데이트일은 Deal 등록일이다
    assert last_updated == created


async def test_editing_an_action_keeps_last_updated(action_env: ActionEnv) -> None:
    """Action 내용을 수정해도 최종 업데이트일은 처음 수행한 날짜 그대로다.

    테스트 코드: RK-007
    """
    # given: 등록+1일에 수행한 Action이 있는 Deal이다
    action = await action_env.act(advance=DAY)
    performed_on = action.acted_on
    action_env.env.clock.advance(2 * DAY)

    # when: 등록+3일에 그 Action의 내용을 수정한다
    await action_env.update_as(action.id, KIM, action="수정한 진행사항")
    last_updated = await _last_updated(action_env)

    # then: 최종 업데이트는 여전히 등록+1일(수행일)이다
    assert last_updated == performed_on


async def test_changing_the_next_action_status_keeps_last_updated(action_env: ActionEnv) -> None:
    """Next Action 상태를 바꿔도 최종 업데이트일은 처음 수행한 날짜 그대로다.

    테스트 코드: RK-007
    """
    # given: 등록+1일에 수행한 Next Action(Due 01-15)이 있는 Deal이다
    action = await action_env.act(advance=DAY, due_date=date(2026, 1, 15))
    performed_on = action.acted_on
    action_env.env.clock.advance(2 * DAY)

    # when: 등록+3일에 Next Action 상태를 done으로 바꾼다
    await action_env.set_status(action.id, KIM, "done")
    last_updated = await _last_updated(action_env)

    # then: 최종 업데이트는 여전히 등록+1일(수행일)이다
    assert last_updated == performed_on
