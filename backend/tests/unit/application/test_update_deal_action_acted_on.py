"""UpdateDealAction의 수행일(`acted_on`): 수정에서 수행일 변경·유지·범위·판정 순서·파생 값.

공통 예: 업무 시간대 Asia/Seoul, 서버 시계 T = 2026-11-13T14:30+09:00, Deal 등록 2026-11-01 09:00.
Action은 모두 KIM이 남겼고 기본 내용의 요약은 SUMMARY_WITH_MEMO다(수정에서 수행일 부분이 붙는다).
"""

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import pytest

from app.application.choice import CatalogChoice
from app.application.ports.deal_action_repository import DealActionQuery
from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import InvalidValueError
from app.domain.deal_action.errors import DealActionEditForbiddenError, DealActionNotFoundError
from app.domain.deal_action.next_action_status import NextActionStatus
from app.domain.deal_action.value_objects import DealActionId
from tests.factories import make_deal_action
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.action_env import (
    ACTION_OR_NEXT_REQUIRED,
    EDIT_FORBIDDEN,
    KIM,
    NOT_FOUND,
    PARK,
    SUMMARY_WITH_MEMO,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.ports.deal_repository import DealListItem
    from app.domain.deal.history import DealHistoryEntry
    from app.domain.deal_action.entities import DealAction
    from tests.unit.application.action_env import ActionEnv

KST = timezone(timedelta(hours=9))
T = datetime(2026, 11, 13, 14, 30, tzinfo=KST)
TODAY = date(2026, 11, 13)
PAST = date(2026, 11, 10)
FUTURE = "수행일은 오늘 이후로 지정할 수 없습니다."
BEFORE_REGISTERED = "수행일은 Deal 등록일(2026-11-01) 이전으로 지정할 수 없습니다."
SUMMARY_PROPOSAL = SUMMARY_WITH_MEMO.replace("킥오프 미팅", "제안 발표")


def _at(day: int, hour: int = 10, month: int = 11) -> datetime:
    return datetime(2026, month, day, hour, 0, tzinfo=KST)


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


@pytest.fixture
async def code(action_env: ActionEnv) -> str:
    """2026-11-01 09:00에 등록된 Deal을 만들고 서버 시계를 T로 맞춘다."""
    action_env.set_clock(_at(1, 9))
    view = await action_env.env.new_deal()
    action_env.set_clock(T)
    return view.item.deal.id.value


async def _given_action(
    action_env: ActionEnv,
    code: str,
    moment: datetime,
    **content: Any,  # noqa: ANN401
) -> DealAction:
    """주어진 시각에 이미 등록돼 있는 KIM의 Action을 만들고 시계를 T로 되돌린다."""
    action_env.set_clock(moment)
    action = await action_env.act(KIM, code=code, advance=0, **content)
    action_env.set_clock(T)
    return action


async def _action_entries(action_env: ActionEnv, code: str) -> list[DealHistoryEntry]:
    """그 Deal의 Action 이력(오래된 순). `action_env.action_entries()`는 기본 Deal만 읽는다."""
    return [e for e in await action_env.entries(code) if str(e.draft.category) == "action"]


async def _listed(action_env: ActionEnv, code: str) -> list[DealAction]:
    from app.domain.deal.code import DealCode  # noqa: PLC0415

    return list(await action_env.list.execute(DealActionQuery(deal_code=DealCode(code))))


async def _deal_row(action_env: ActionEnv, code: str) -> DealListItem:
    (row,) = (await action_env.env.list.execute(DealQuery(keyword=code))).items
    return row.item


async def test_changing_only_the_acted_on_updates_it_and_logs_one_entry(
    action_env: ActionEnv, code: str
) -> None:
    """수행일만 고치면 수행일·수정 시각만 바뀌고 수행일이 붙은 이력 1건이 남는다.

    테스트 코드: AC-118
    """
    # given: 오늘(11-13) 수행일로 등록된 Action과 수정 전 이력 건수
    action = await action_env.act(KIM, code=code, advance=0)
    entries_before = len(await _action_entries(action_env, code))
    deal_before = await action_env.env.uow.deals.get(action_env.deal.item.deal.id)

    # when: KIM이 내용은 그대로 두고 수행일만 11-10으로 고친다
    updated = await action_env.update_as(action.id, KIM, acted_on=PAST)

    # then: 수행일이 11-10이고 수정 시각은 요청 시각이다
    stored = await action_env.stored(action.id)
    assert stored.acted_on == PAST
    assert stored.updated_at == updated.updated_at == action_env.env.clock.now()
    # then: 내용·담당자·스냅숏·등록 시각·Next Action 상태는 그대로다
    assert stored.content == action.content
    assert (stored.actor_user_id, stored.snapshot) == (action.actor_user_id, action.snapshot)
    assert stored.created_at == action.created_at
    assert stored.next_action_state == action.next_action_state
    # then: Deal 수정 시각이 그대로다
    deal_after = await action_env.env.uow.deals.get(action_env.deal.item.deal.id)
    assert deal_after.updated_at == deal_before.updated_at
    # then: 이력 1건이 늘고 변경 전·후 끝에 수행일이 붙는다
    entries = await _action_entries(action_env, code)
    assert len(entries) == entries_before + 1
    assert (await action_env.rows(code))[-1] == (
        "action",
        "Action",
        f"{SUMMARY_WITH_MEMO} / 수행일: 2026-11-13",
        f"수정: {SUMMARY_WITH_MEMO} / 수행일: 2026-11-10",
    )
    assert entries[-1].changed_by == KIM.user_id


async def test_changing_the_acted_on_and_the_content_together_logs_one_entry_with_both(
    action_env: ActionEnv, code: str
) -> None:
    """수행일과 내용을 함께 고치면 이력 1건에 둘 다 반영된다.

    테스트 코드: AC-119
    """
    # given: 오늘 수행일로 등록된 Action과 수정 전 이력 건수
    action = await action_env.act(KIM, code=code, advance=0)
    entries_before = len(await _action_entries(action_env, code))

    # when: 진행사항과 수행일(11-10)을 함께 고친다
    await action_env.update_as(action.id, KIM, acted_on=PAST, action="제안 발표")

    # then: 내용과 수행일이 모두 바뀐다
    stored = await action_env.stored(action.id)
    assert (stored.content.action, stored.acted_on) == ("제안 발표", PAST)
    # then: 이력은 1건 늘고 변경 전·후 요약과 수행일이 한 줄에 있다
    assert len(await _action_entries(action_env, code)) == entries_before + 1
    assert (await action_env.rows(code))[-1][2:] == (
        f"{SUMMARY_WITH_MEMO} / 수행일: 2026-11-13",
        f"수정: {SUMMARY_PROPOSAL} / 수행일: 2026-11-10",
    )


@pytest.mark.parametrize("acted_on", [None, TODAY], ids=["omitted-or-null", "same-date"])
async def test_omitted_or_same_acted_on_with_same_content_changes_nothing(
    action_env: ActionEnv, code: str, acted_on: date | None
) -> None:
    """수행일을 생략·null·같은 날짜로 보내고 내용도 같으면 저장도 이력도 없다.

    테스트 코드: AC-120
    """
    # given: 오늘 수행일로 등록된 Action과 수정 전 이력
    action = await action_env.act(KIM, code=code, advance=0)
    rows_before = await action_env.rows(code)

    # when: 같은 내용에 수행일을 생략(또는 지금과 같은 날짜)으로 고친다
    result = await action_env.update_as(action.id, KIM, acted_on=acted_on)

    # then: 수행일·수정 시각·이력이 그대로다
    stored = await action_env.stored(action.id)
    assert stored.acted_on == TODAY
    assert stored.updated_at == result.updated_at == action.updated_at
    assert await action_env.rows(code) == rows_before


async def test_omitted_acted_on_keeps_it_when_only_the_content_changes(
    action_env: ActionEnv, code: str
) -> None:
    """수행일을 보내지 않고 내용만 고치면 수행일은 그대로이고 이력에 수행일 부분이 없다.

    테스트 코드: AC-120, AC-103
    """
    # given: 지난 수행일(11-10)로 등록된 Action
    action = await action_env.act(KIM, code=code, advance=0, acted_on=PAST)

    # when: 수행일 없이 진행사항만 고친다
    await action_env.update_as(action.id, KIM, action="제안 발표")

    # then: 수행일은 11-10 그대로다
    assert (await action_env.stored(action.id)).acted_on == PAST
    # then: 이력에는 수행일 부분이 붙지 않는다
    assert (await action_env.rows(code))[-1][2:] == (SUMMARY_WITH_MEMO, f"수정: {SUMMARY_PROPOSAL}")


async def test_same_acted_on_is_not_range_checked_even_if_it_is_out_of_range(
    action_env: ActionEnv, code: str
) -> None:
    """지금과 같은 날짜는 범위 판정 없이 받는다(내용만 고친 것과 같다).

    테스트 코드: AC-120
    """
    # given: Deal 등록일(11-01)보다 앞선 수행일(10-20)을 가진 Action이 저장돼 있다
    old = make_deal_action(
        deal_code=action_env.deal.item.deal.id,
        actor_user_id=KIM.user_id,
        acted_on=date(2026, 10, 20),
    )
    await action_env.env.uow.deal_actions.add(old)

    # when: 같은 날짜(10-20)를 보내며 진행사항을 고친다
    await action_env.update_as(old.id, KIM, acted_on=date(2026, 10, 20), action="다시 정리")

    # then: 거절되지 않고 내용만 바뀌며 수행일은 그대로다
    stored = await action_env.stored(old.id)
    assert stored.content.action == "다시 정리"
    assert stored.acted_on == date(2026, 10, 20)


async def test_tomorrow_as_the_acted_on_is_rejected_and_nothing_changes(
    action_env: ActionEnv, code: str
) -> None:
    """수정 수행일이 내일이면 422이고 Action·이력·새 유형이 그대로다.

    테스트 코드: AC-121
    """
    # given: 지난 수행일로 등록된 Action, 수정 전 이력·유형 목록
    action = await action_env.act(KIM, code=code, advance=0, acted_on=PAST)
    rows_before = await action_env.rows(code)
    types_before = [t.name for t in await action_env.env.uow.action_types.list()]

    # when·then: 새 유형과 함께 내일(11-14) 수행일로 고치면 수행일 오류다
    with raises_with(InvalidValueError, FUTURE):
        await action_env.update_as(
            action.id, KIM, acted_on=date(2026, 11, 14), action_type=CatalogChoice(name="새 유형")
        )

    # then: Action·이력·유형 목록이 그대로다
    stored = await action_env.stored(action.id)
    assert (stored.acted_on, stored.content, stored.updated_at) == (
        PAST,
        action.content,
        action.updated_at,
    )
    assert await action_env.rows(code) == rows_before
    assert [t.name for t in await action_env.env.uow.action_types.list()] == types_before


async def test_today_as_the_acted_on_is_accepted(action_env: ActionEnv, code: str) -> None:
    """수정 수행일이 오늘이면 받는다.

    테스트 코드: AC-121
    """
    # given: 지난 수행일(11-10)로 등록된 Action
    action = await action_env.act(KIM, code=code, advance=0, acted_on=PAST)

    # when: 수행일을 오늘(11-13)로 고친다
    await action_env.update_as(action.id, KIM, acted_on=TODAY)

    # then: 수행일이 오늘이다
    assert (await action_env.stored(action.id)).acted_on == TODAY


async def test_acted_on_before_the_deal_registration_day_is_rejected_on_update(
    action_env: ActionEnv, code: str
) -> None:
    """수정 수행일이 Deal 등록일 전날이면 422이고 Action·이력이 그대로다.

    테스트 코드: AC-122
    """
    # given: 오늘 수행일로 등록된 Action과 수정 전 이력
    action = await action_env.act(KIM, code=code, advance=0)
    rows_before = await action_env.rows(code)

    # when·then: 등록일(11-01) 전날 10-31로 고치면 수행일 오류다
    with raises_with(InvalidValueError, BEFORE_REGISTERED):
        await action_env.update_as(action.id, KIM, acted_on=date(2026, 10, 31))

    # then: 수행일·이력이 그대로다
    assert (await action_env.stored(action.id)).acted_on == TODAY
    assert await action_env.rows(code) == rows_before


async def test_acted_on_on_the_deal_registration_day_is_accepted_on_update(
    action_env: ActionEnv, code: str
) -> None:
    """수정 수행일이 Deal 등록일 당일이면 받는다.

    테스트 코드: AC-122
    """
    # given: 오늘 수행일로 등록된 Action
    action = await action_env.act(KIM, code=code, advance=0)

    # when: 수행일을 등록일 당일(11-01)로 고친다
    await action_env.update_as(action.id, KIM, acted_on=date(2026, 11, 1))

    # then: 수행일이 11-01이다
    assert (await action_env.stored(action.id)).acted_on == date(2026, 11, 1)


async def test_update_checks_missing_then_owner_before_the_acted_on(
    action_env: ActionEnv, code: str
) -> None:
    """수정 판정은 없는 Action 404가 담당자 403보다, 403이 수행일 422보다 먼저다.

    테스트 코드: AC-123
    """
    # given: KIM의 Action
    action = await action_env.act(KIM, code=code, advance=0)

    # when·then: 없는 id는 내일 수행일이어도 Action 없음 오류다
    with raises_with(DealActionNotFoundError, NOT_FOUND):
        await action_env.update_as(DealActionId(new_id()), PARK, acted_on=date(2026, 11, 14))
    # when·then: 남의 Action은 내일 수행일이어도 수정 권한 오류다
    with raises_with(DealActionEditForbiddenError, EDIT_FORBIDDEN):
        await action_env.update_as(action.id, PARK, acted_on=date(2026, 11, 14))


async def test_update_content_error_comes_before_the_acted_on_error(
    action_env: ActionEnv, code: str
) -> None:
    """내용 오류와 수행일 오류가 함께 있으면 내용 오류가 먼저다.

    테스트 코드: AC-123
    """
    # given: KIM의 Action
    action = await action_env.act(KIM, code=code, advance=0)

    # when·then: 진행사항·Next Action을 비우고 내일 수행일로 고치면 내용 오류다
    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        await action_env.update_as(
            action.id,
            KIM,
            acted_on=date(2026, 11, 14),
            action="",
            next_action="",
            due_date=None,
        )


async def test_update_rejected_for_the_acted_on_leaves_no_new_type(
    action_env: ActionEnv, code: str
) -> None:
    """수행일로 거절돼도 같은 요청의 새 유형은 남지 않고, 유형 오류는 수행일 오류보다 먼저다.

    테스트 코드: AC-123
    """
    # given: KIM의 Action과 수정 전 유형 목록
    action = await action_env.act(KIM, code=code, advance=0)
    types_before = [t.name for t in await action_env.env.uow.action_types.list()]

    # when·then: 빈 유형 이름은 내일 수행일이어도 유형 오류다
    with raises_with(InvalidValueError, "유형을 입력하세요."):
        await action_env.update_as(
            action.id, KIM, acted_on=date(2026, 11, 14), action_type=CatalogChoice(name="  ")
        )
    # when·then: 새 유형 이름 + 등록일 이전 수행일은 수행일 오류다
    with raises_with(InvalidValueError, BEFORE_REGISTERED):
        await action_env.update_as(
            action.id, KIM, acted_on=date(2026, 10, 31), action_type=CatalogChoice(name="웨비나")
        )

    # then: 어느 쪽도 새 유형을 남기지 않는다
    assert [t.name for t in await action_env.env.uow.action_types.list()] == types_before


async def test_changing_the_acted_on_recalculates_next_action_last_updated_and_list_order(
    action_env: ActionEnv, code: str
) -> None:
    """수행일을 고치면 Deal의 Next Action·최종 업데이트일·목록 순서가 다시 계산된다.

    테스트 코드: AC-125
    """
    # given: 11-12 수행의 "A계획"(기준 행, 최근)과 11-05 수행의 "B계획" Action
    await _given_action(action_env, code, _at(12), action="최근", next_action="A계획")
    older = await _given_action(action_env, code, _at(5), action="오래된", next_action="B계획")
    item = await _deal_row(action_env, code)
    assert item.next_action is not None
    assert (item.next_action.text, item.last_updated_on) == ("A계획", date(2026, 11, 12))

    # when: 오래된 Action의 수행일을 오늘(11-13)로 고친다
    await action_env.update_as(older.id, KIM, acted_on=TODAY, action="오래된", next_action="B계획")

    # then: Next Action은 "B계획", 최종 업데이트일은 11-13이다
    item = await _deal_row(action_env, code)
    assert item.next_action is not None
    assert (item.next_action.text, item.last_updated_on) == ("B계획", TODAY)
    # then: 목록 순서는 11-13 → 11-12다
    assert [str(a.content.action) for a in await _listed(action_env, code)] == ["오래된", "최근"]

    # when: 같은 Action의 수행일을 다시 11-02로 낮춘다
    await action_env.update_as(
        older.id, KIM, acted_on=date(2026, 11, 2), action="오래된", next_action="B계획"
    )

    # then: 기준 행·최종 업데이트일·목록 순서가 다시 "A계획"/11-12/최근 먼저가 된다
    item = await _deal_row(action_env, code)
    assert item.next_action is not None
    assert (item.next_action.text, item.last_updated_on) == ("A계획", date(2026, 11, 12))
    assert [str(a.content.action) for a in await _listed(action_env, code)] == ["최근", "오래된"]


async def test_the_acted_on_is_not_compared_with_the_closed_date_or_the_action_it_closed(
    action_env: ActionEnv, code: str
) -> None:
    """수정 수행일은 종료일·자기가 닫은 Action·기준 행의 수행일과 선후를 따지지 않는다.

    테스트 코드: AC-126
    """
    # given: 11-12 수행의 기준 행 X, X를 닫으며 오늘 등록한 Y, 그리고 종료(수행)한 Y
    basis = await _given_action(action_env, code, _at(12))
    closing = await action_env.act(KIM, code=code, advance=0, close_previous=basis.id)
    await action_env.set_status(closing.id, KIM, "done")
    closed_state = (await action_env.stored(closing.id)).next_action_state

    # when: Y의 수행일을 X의 수행일(11-12)과 자기 종료일(11-13)보다 앞선 11-02로 고친다
    await action_env.update_as(closing.id, KIM, acted_on=date(2026, 11, 2))

    # then: 거절되지 않고 Y의 수행일만 바뀐다
    stored = await action_env.stored(closing.id)
    assert stored.acted_on == date(2026, 11, 2)
    # then: Y의 종료 상태·종료일과 X의 종료(수행) 상태는 그대로다
    assert stored.next_action_state == closed_state
    assert stored.next_action_state is not None
    assert stored.next_action_state.status is NextActionStatus.DONE
    state = (await action_env.stored(basis.id)).next_action_state
    assert state is not None
    assert state.status is NextActionStatus.DONE
