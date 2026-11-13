"""같은 수행일 Action의 순서(AC-R43): 수행일이 같으면 id가 큰, 나중에 등록한 Action이 더 최근이다.

기준 행(RK-R1)·기본 목록(AC-R18)·수행일 내림차순은 (수행일, id) 내림차순이고 오름차순은 그 반대다.
수행일은 날짜뿐이라 같은 날 안의 시각이 순서에 영향을 주지 않는다.
"""

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_action_repository import DealActionQuery, DealActionSort
from app.application.ports.deal_repository import DealQuery
from app.domain.deal.code import DealCode
from tests.unit.application.action_env import KIM

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.unit.application.action_env import ActionEnv

KST = timezone(timedelta(hours=9))
DAY = date(2026, 11, 10)


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


@pytest.fixture
async def code(action_env: ActionEnv) -> str:
    """2026-11-01 09:00에 등록된 Deal을 만들고 서버 시계를 11-13 14:30으로 맞춘다."""
    action_env.set_clock(datetime(2026, 11, 1, 9, 0, tzinfo=KST))
    view = await action_env.env.new_deal()
    action_env.set_clock(datetime(2026, 11, 13, 14, 30, tzinfo=KST))
    return view.item.deal.id.value


async def _listed(action_env: ActionEnv, code: str, sort: DealActionSort) -> list[str]:
    query = DealActionQuery(deal_code=DealCode(code), sort=sort)
    return [str(a.content.next_action) for a in await action_env.list.execute(query)]


async def test_the_later_registered_action_of_the_same_day_is_the_basis_and_sorts_last_ascending(
    action_env: ActionEnv, code: str
) -> None:
    """같은 수행일의 Next Action Action은 나중에 등록한 것이 기준 행이고 오름차순에서는 뒤에 온다.

    테스트 코드: AC-111
    """
    # given: 같은 수행일(11-10)에 Next Action이 있는 Action 둘을 먼저·나중 순서로 등록한다
    first = await action_env.act(KIM, code=code, advance=0, acted_on=DAY, next_action="먼저")
    second = await action_env.act(KIM, code=code, advance=0, acted_on=DAY, next_action="나중")
    assert second.id > first.id

    # when: Deal 목록의 Next Action과 내림차순·오름차순 Action 목록을 읽는다
    (row,) = (await action_env.env.list.execute(DealQuery(keyword=code))).items
    descending = await _listed(action_env, code, DealActionSort.ACTED_AT_DESC)
    ascending = await _listed(action_env, code, DealActionSort.ACTED_AT_ASC)

    # then: 기준 행은 나중에 등록한 것이고 내림차순은 나중이 앞, 오름차순은 나중이 뒤다
    assert row.item.next_action is not None
    assert row.item.next_action.text == "나중"
    assert descending == ["나중", "먼저"]
    assert ascending == ["먼저", "나중"]


async def test_the_order_follows_the_id_even_when_the_clock_time_is_earlier(
    action_env: ActionEnv, code: str
) -> None:
    """같은 수행일이면 등록 시각이 이르더라도 id가 큰 Action이 더 최근이다(시각은 순서에 안 쓰인다).

    테스트 코드: AC-111
    """
    # given: 14:30에 먼저 등록한 Action과, 시계를 09:00으로 돌려 나중에 등록한 같은 수행일 Action
    today = date(2026, 11, 13)
    await action_env.act(KIM, code=code, advance=0, next_action="먼저(14:30)")
    action_env.set_clock(datetime(2026, 11, 13, 9, 0, tzinfo=KST))
    await action_env.act(KIM, code=code, advance=0, acted_on=today, next_action="나중(09:00)")

    # when: Deal 목록의 Next Action과 기본 목록을 읽는다
    (row,) = (await action_env.env.list.execute(DealQuery(keyword=code))).items
    descending = await _listed(action_env, code, DealActionSort.ACTED_AT_DESC)

    # then: id가 큰 쪽이 기준 행이고 목록 맨 위다
    assert row.item.next_action is not None
    assert row.item.next_action.text == "나중(09:00)"
    assert descending == ["나중(09:00)", "먼저(14:30)"]


async def test_a_later_date_beats_a_larger_id(action_env: ActionEnv, code: str) -> None:
    """수행일이 다르면 id와 관계없이 더 늦은 수행일이 더 최근이다.

    테스트 코드: AC-111
    """
    # given: 수행일 11-12 Action을 먼저, 수행일 11-10 Action을 나중에(더 큰 id로) 등록한다
    await action_env.act(
        KIM, code=code, advance=0, acted_on=date(2026, 11, 12), next_action="늦은 날"
    )
    await action_env.act(KIM, code=code, advance=0, acted_on=DAY, next_action="이른 날")

    # when: Deal 목록의 Next Action과 내림차순 목록을 읽는다
    (row,) = (await action_env.env.list.execute(DealQuery(keyword=code))).items
    descending = await _listed(action_env, code, DealActionSort.ACTED_AT_DESC)

    # then: 수행일이 늦은 쪽이 기준 행이고 앞이다
    assert row.item.next_action is not None
    assert row.item.next_action.text == "늦은 날"
    assert descending == ["늦은 날", "이른 날"]
