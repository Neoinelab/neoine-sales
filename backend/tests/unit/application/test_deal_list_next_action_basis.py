"""Deal 목록(DL) BDD 케이스 — Next Action 기준 행(RK-R1)이 상태 필터·목록 행·CSV에서 같다.

`ListDeals`·`ExportDeals`를 When으로 부르고 저장소·시계는 모두 Fake다. "오늘"은 서버 시계를
Asia/Seoul 날짜로 바꾼 값이고 `_today`가 2026-01-10으로 맞춘다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_action_repository import NextActionStatusFilter
from app.application.ports.deal_repository import DealQuery
from app.domain.deal_action.next_action_status import NextActionStatus
from app.domain.deal_action.value_objects import DealActionId
from tests.factories import make_deal_action
from tests.support.user_ids import ACTOR_ID

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.deal.dto import DealPage, DealView
    from app.domain.deal_action.entities import DealAction
    from tests.unit.application.deal_env import DealEnv

DAY = 24 * 3600
CSV_NEXT_ACTION, CSV_DUE, CSV_STATUS = 11, 12, 13  # CSV 머리글의 Next Action·Due·상태 열


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def _act(  # noqa: PLR0913 - 행 하나를 정하는 독립된 값들
    env: DealEnv,
    view: DealView,
    row_id: int,
    *,
    acted_on: date,
    text: str,
    due: date,
    status: NextActionStatus = NextActionStatus.OPEN,
) -> DealAction:
    action = make_deal_action(
        deal_code=view.item.deal.id,
        now=env.clock.now(),
        actor_user_id=ACTOR_ID,
        acted_on=acted_on,
        entity_id=DealActionId(row_id),
        next_action=text,
        due_date=due,
    )
    await env.uow.deal_actions.add(action)
    if status is not NextActionStatus.OPEN:
        action.change_next_action_status(status, "", env.clock.now())
        await env.uow.deal_actions.update(action)
    return action


async def _deals(env: DealEnv) -> dict[str, DealView]:
    """DL-126의 P·Q·R. 오늘 2026-01-10."""
    deals = {
        "P": await env.new_deal(name="P"),
        "Q": await env.new_deal(name="Q"),
        "R": await env.new_deal(name="R"),
    }
    done = NextActionStatus.DONE
    await _act(
        env, deals["P"], 501, acted_on=date(2026, 1, 2), text="견적 발송", due=date(2026, 1, 5)
    )
    await _act(
        env,
        deals["P"],
        502,
        acted_on=date(2026, 1, 9),
        text="데모",
        due=date(2026, 1, 20),
        status=done,
    )
    await _act(
        env,
        deals["Q"],
        503,
        acted_on=date(2026, 1, 9),
        text="검토",
        due=date(2026, 1, 20),
        status=done,
    )
    await _act(env, deals["R"], 504, acted_on=date(2026, 1, 9), text="회신", due=date(2026, 1, 30))
    env.clock.advance(9 * DAY)  # 오늘 = 01-10
    return deals


def _names(page: DealPage) -> list[str]:
    return sorted(view.item.deal.details.name for view in page.items)


@pytest.mark.parametrize(
    ("wanted", "names"),
    [
        (NextActionStatusFilter.OPEN, ["P", "R"]),
        (NextActionStatusFilter.DONE, ["Q"]),
        (NextActionStatusFilter.CLOSED, ["Q"]),
        (NextActionStatusFilter.NOT_DONE, []),
    ],
)
async def test_status_filter_uses_the_past_open_basis_row_and_total_matches(
    env: DealEnv, wanted: NextActionStatusFilter, names: list[str]
) -> None:
    """next_action_status는 기한초과 Deal을 지난 Open 기준 행의 상태(open)로 거르고 total도 같다.

    테스트 코드: DL-126
    """
    # given: 오늘 01-10. P는 지난 Open A와 최근 done B, Q는 done 하나, R은 미래 Open 하나다
    await _deals(env)

    # when: 상태 필터로 목록을 조회한다
    page = await env.list.execute(DealQuery(next_action_status=wanted))

    # then: open은 P·R, done·closed는 Q만이고 total이 같다
    assert _names(page) == names
    assert page.total == len(names)


async def test_overdue_row_shows_the_open_basis_with_its_action_id(env: DealEnv) -> None:
    """P 행의 next_action은 지난 Open 행 A(status open)이고 action_id가 A다.

    테스트 코드: DL-126
    """
    # given: DL-126의 P·Q·R
    await _deals(env)

    # when: open 필터로 목록을 조회한다
    page = await env.list.execute(DealQuery(next_action_status=NextActionStatusFilter.OPEN))

    # then: P 행의 next_action은 A(견적 발송, open, action_id 501)이다
    row = next(v for v in page.items if v.item.deal.details.name == "P")
    assert row.item.next_action is not None
    assert row.item.next_action.text == "견적 발송"
    assert row.item.next_action.status is NextActionStatus.OPEN
    assert row.item.next_action.action_id == DealActionId(501)


async def test_list_row_and_csv_columns_show_the_same_basis_row(env: DealEnv) -> None:
    """목록 행과 CSV의 Next Action·Due·Next Action 상태는 같은 기준 행이다.

    테스트 코드: DL-127
    """
    # given: DL-126의 P(지난 Open A 우선)와 Q(done 하나)
    await _deals(env)
    query = DealQuery()

    # when: 같은 조건으로 목록과 CSV를 만든다
    page = await env.list.execute(query)
    export = await env.export.execute(query)

    # then: P의 CSV 칸은 A의 내용·2026-01-05·Open이고 목록 행 next_action과 같다
    rows = {row[0]: row for row in export.rows}
    listed = {v.item.deal.details.name: v.item.next_action for v in page.items}
    assert rows["P"][CSV_NEXT_ACTION] == "견적 발송"
    assert rows["P"][CSV_DUE] == "2026-01-05"
    assert rows["P"][CSV_STATUS] == "Open"
    assert listed["P"] is not None
    assert (listed["P"].text, str(listed["P"].due_date)) == ("견적 발송", "2026-01-05")
    # then: Q의 칸은 그 행의 내용·2026-01-20·종료(수행)이다
    assert rows["Q"][CSV_NEXT_ACTION] == "검토"
    assert rows["Q"][CSV_DUE] == "2026-01-20"
    assert rows["Q"][CSV_STATUS] == "종료(수행)"
    assert listed["Q"] is not None
    assert listed["Q"].status is NextActionStatus.DONE


async def test_csv_with_the_status_filter_matches_the_list_total(env: DealEnv) -> None:
    """상태 필터를 건 CSV도 같은 기준 행으로 걸러 목록 total과 같은 행을 낸다.

    테스트 코드: DL-127
    """
    # given: DL-126의 P·Q·R
    await _deals(env)
    query = DealQuery(next_action_status=NextActionStatusFilter.OPEN)

    # when: 같은 조건으로 목록과 CSV를 만든다
    page = await env.list.execute(query)
    export = await env.export.execute(query)

    # then: CSV는 P·R이고 건수가 목록 total과 같다
    assert sorted(row[0] for row in export.rows) == ["P", "R"]
    assert len(export.rows) == page.total
