"""RegisterDealAction의 수행일(`acted_on`): 수행일 결정·범위·이전 Next Action 종료·요청 시각.

수행일은 날짜만 저장한다(시각 없음, AC-R34). 등록·수정 시각·이력 시각은 요청 시각이다(AC-R37).

공통 예: 업무 시간대 Asia/Seoul, 서버 시계 T = 2026-11-13T14:30+09:00, Deal 등록 2026-11-01 09:00.
"""

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import pytest

from app.application.deal_action.inputs import StatusChangeInput
from app.application.ports.deal_action_repository import DealActionQuery
from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import InvalidValueError
from app.domain.deal_action.next_action_status import NextActionState, NextActionStatus
from tests.support.expect import raises_with
from tests.unit.application.action_env import ACTION_OR_NEXT_REQUIRED, KIM, PARK

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.ports.deal_repository import DealListItem
    from app.domain.deal_action.entities import DealAction
    from tests.unit.application.action_env import ActionEnv

KST = timezone(timedelta(hours=9))
T = datetime(2026, 11, 13, 14, 30, tzinfo=KST)
TODAY = date(2026, 11, 13)
PAST = date(2026, 11, 10)
FUTURE = "수행일은 오늘 이후로 지정할 수 없습니다."
BEFORE_REGISTERED = "수행일은 Deal 등록일(2026-11-01) 이전으로 지정할 수 없습니다."


def _too_early(day: str) -> str:
    return (
        f"이전 Next Action의 수행일({day})보다 앞선 날짜로는 이전 Next Action을 종료할 수 없습니다."
    )


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


async def _listed(action_env: ActionEnv, code: str) -> list[DealAction]:
    from app.domain.deal.code import DealCode  # noqa: PLC0415

    return list(await action_env.list.execute(DealActionQuery(deal_code=DealCode(code))))


async def _deal_row(action_env: ActionEnv, code: str) -> DealListItem:
    (row,) = (await action_env.env.list.execute(DealQuery(keyword=code))).items
    return row.item


@pytest.mark.parametrize("acted_on", [None, TODAY], ids=["omitted-or-null", "today"])
async def test_no_or_todays_acted_on_records_the_request_time(
    action_env: ActionEnv, code: str, acted_on: date | None
) -> None:
    """수행일을 생략·null·오늘로 보내면 수행일은 오늘(요청의 업무 날짜)이다.

    테스트 코드: AC-091
    """
    # when: KIM이 수행일 없이(또는 오늘로) 기본 Action을 등록한다 (전제: 서버 시계 T)
    action = await action_env.act(KIM, code=code, advance=0, acted_on=acted_on)

    # then: 수행일은 오늘이고 등록·수정 시각은 요청 시각 T다
    stored = await action_env.stored(action.id)
    assert stored.acted_on == TODAY
    assert stored.created_at == stored.updated_at == T


async def test_past_acted_on_records_that_date_but_keeps_request_time_elsewhere(
    action_env: ActionEnv, code: str
) -> None:
    """지난 수행일로 등록하면 수행일은 그 날짜(시각 없음)이고 등록·수정·이력 시각은 요청 시각이다.

    테스트 코드: AC-092
    """
    # when: KIM이 2026-11-10 수행일로 기본 Action을 등록한다 (전제: 서버 시계 T)
    action = await action_env.act(KIM, code=code, advance=0, acted_on=date(2026, 11, 10))

    # then: 수행일은 11-10(date)이고 등록·수정 시각은 T다
    stored = await action_env.stored(action.id)
    assert stored.acted_on == PAST
    assert stored.created_at == stored.updated_at == T
    # then: 등록 이력의 시각은 T다
    (entry,) = [e for e in await action_env.entries(code) if str(e.draft.category) == "action"]
    assert entry.changed_at == T


async def test_tomorrow_as_acted_on_is_rejected_and_nothing_is_saved(
    action_env: ActionEnv, code: str
) -> None:
    """내일 수행일은 422이고 아무것도 저장되지 않는다.

    테스트 코드: AC-093
    """
    # given: 등록 전의 유형 목록과 Deal 이력
    types_before = [t.name for t in await action_env.env.uow.action_types.list()]
    history_before = await action_env.rows(code)

    # when·then: 새 유형으로 내일 수행일 등록은 InvalidValueError다
    with raises_with(InvalidValueError, FUTURE):
        await action_env.act(
            KIM, code=code, advance=0, acted_on=date(2026, 11, 14), action_type="새 유형"
        )

    # then: Action·이력·새 유형이 없다
    assert await _listed(action_env, code) == []
    assert await action_env.rows(code) == history_before
    assert [t.name for t in await action_env.env.uow.action_types.list()] == types_before


async def test_acted_on_before_the_deal_registration_day_is_rejected(
    action_env: ActionEnv, code: str
) -> None:
    """Deal 등록일 전날 수행일은 422이고 아무것도 저장되지 않는다.

    테스트 코드: AC-094
    """
    # when·then: 등록일(11-01) 전날인 10-31로 등록하면 InvalidValueError다
    with raises_with(InvalidValueError, BEFORE_REGISTERED):
        await action_env.act(KIM, code=code, advance=0, acted_on=date(2026, 10, 31))

    # then: 저장된 Action이 없다
    assert await _listed(action_env, code) == []


async def test_acted_on_on_the_deal_registration_day_is_accepted(
    action_env: ActionEnv, code: str
) -> None:
    """Deal 등록일 당일 수행일은 등록된다.

    테스트 코드: AC-094
    """
    # when: 등록일 당일(11-01)을 수행일로 등록한다 (전제: 서버 시계 T)
    action = await action_env.act(KIM, code=code, advance=0, acted_on=date(2026, 11, 1))

    # then: 수행일은 2026-11-01이다
    assert (await action_env.stored(action.id)).acted_on == date(2026, 11, 1)


async def test_acted_on_is_checked_after_content_errors_and_before_previous_next_action(
    action_env: ActionEnv, code: str
) -> None:
    """수행일 판정은 내용 오류 다음, 이전 Next Action 409 앞이다.

    테스트 코드: AC-096
    """
    # given: 기준 행이 아닌 id(다른 Deal 아닌, 더 오래된 Action)를 가리킬 수 있는 두 Action
    old = await _given_action(action_env, code, _at(5))
    await _given_action(action_env, code, _at(6), next_action="최신 계획")

    # when·then: 내용이 모두 비고 내일 수행일이면 내용 오류가 먼저다
    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        await action_env.act(
            KIM, code=code, advance=0, acted_on=date(2026, 11, 14), action="", next_action=""
        )

    # when·then: 내용이 맞고 기준 행이 아닌 id를 닫으려 해도 수행일 422가 먼저다(409 아님)
    with raises_with(InvalidValueError, FUTURE):
        await action_env.act(
            KIM, code=code, advance=0, acted_on=date(2026, 11, 14), close_previous=old.id
        )


async def test_a_later_action_keeps_next_action_and_last_updated_when_a_past_one_is_added(
    action_env: ActionEnv, code: str
) -> None:
    """더 늦은 Action이 있으면 지난 날짜 Action은 Deal의 Next Action·최종 업데이트를 바꾸지 않는다.

    테스트 코드: AC-097
    """
    # given: 11-12 10:00에 등록한 Next Action "견적 발송"(Due 11-20) Action
    await _given_action(
        action_env, code, _at(12), next_action="견적 발송", due_date=date(2026, 11, 20)
    )

    # when: 수행일 11-11로 Next Action "자료 전달"(Due 11-15)을 등록한다
    await action_env.act(
        KIM,
        code=code,
        advance=0,
        acted_on=date(2026, 11, 11),
        next_action="자료 전달",
        due_date=date(2026, 11, 15),
    )

    # then: Deal의 Next Action은 "견적 발송", 최종 업데이트일은 11-12 그대로다
    item = await _deal_row(action_env, code)
    assert item.next_action is not None
    assert item.next_action.text == "견적 발송"
    assert item.last_updated_on == date(2026, 11, 12)


async def test_the_latest_past_action_becomes_the_next_action_and_last_updated(
    action_env: ActionEnv, code: str
) -> None:
    """지난 날짜 Action의 수행일이 가장 늦으면 Next Action·최종 업데이트일이 그 Action을 따른다.

    테스트 코드: AC-098
    """
    # given: 11-05 10:00에 등록한 Next Action "견적 발송" Action뿐이다
    await _given_action(action_env, code, _at(5), next_action="견적 발송")

    # when: 수행일 11-10으로 Next Action "자료 전달"(Due 11-15)을 등록한다
    await action_env.act(
        KIM,
        code=code,
        advance=0,
        acted_on=date(2026, 11, 10),
        next_action="자료 전달",
        due_date=date(2026, 11, 15),
    )

    # then: Next Action은 "자료 전달", 최종 업데이트일은 11-10이다
    item = await _deal_row(action_env, code)
    assert item.next_action is not None
    assert item.next_action.text == "자료 전달"
    assert item.last_updated_on == PAST


async def test_default_list_places_a_past_action_at_its_acted_on_position(
    action_env: ActionEnv, code: str
) -> None:
    """기본 목록에서 지난 날짜 Action은 수행일 순서 자리에 놓인다.

    테스트 코드: AC-099
    """
    # given: 11-05 10:00과 11-12 10:00에 등록한 Action
    await _given_action(action_env, code, _at(5), action="오래된")
    await _given_action(action_env, code, _at(12), action="최근")

    # when: 수행일 11-10으로 하나 더 등록하고 조건 없이 목록을 읽는다
    await action_env.act(KIM, code=code, advance=0, acted_on=date(2026, 11, 10), action="중간")
    found = await _listed(action_env, code)

    # then: 순서는 11-12 → 11-10 → 11-05다
    assert [str(a.content.action) for a in found] == ["최근", "중간", "오래된"]
    assert found[1].acted_on == PAST


async def test_closing_with_an_acted_on_before_the_basis_row_is_rejected(
    action_env: ActionEnv, code: str
) -> None:
    """기준 행 수행일보다 앞선 수행일로 이전 Next Action을 닫으면 422이고 기준 행은 Open이다.

    테스트 코드: AC-100
    """
    # given: KIM의 기준 행(Open)이 11-12 10:00에 등록돼 있다
    basis = await _given_action(action_env, code, _at(12))

    # when·then: 수행일 11-11로 그 id를 닫으며 등록하면 InvalidValueError다
    with raises_with(InvalidValueError, _too_early("2026-11-12")):
        await action_env.act(
            KIM, code=code, advance=0, acted_on=date(2026, 11, 11), close_previous=basis.id
        )

    # then: 기준 행은 Open 그대로이고 새 Action은 없다
    assert (await action_env.stored(basis.id)).next_action_state == NextActionState.open()
    assert len(await _listed(action_env, code)) == 1


async def test_closing_with_an_acted_on_on_the_same_day_as_the_basis_row_closes_it(
    action_env: ActionEnv, code: str
) -> None:
    """기준 행과 같은 날 수행일이면 이전 Next Action이 닫힌다.

    테스트 코드: AC-100
    """
    # given: KIM의 기준 행(Open)이 11-12 10:00에 등록돼 있다
    basis = await _given_action(action_env, code, _at(12))

    # when: 수행일 11-12로 그 id를 닫으며 등록한다
    created = await action_env.act(
        KIM, code=code, advance=0, acted_on=date(2026, 11, 12), close_previous=basis.id
    )

    # then: 새 Action이 수행일 11-12로 저장되고 기준 행은 종료(수행)다
    assert (await action_env.stored(created.id)).acted_on == date(2026, 11, 12)
    state = (await action_env.stored(basis.id)).next_action_state
    assert state is not None
    assert state.status is NextActionStatus.DONE


async def test_closing_the_previous_with_a_past_acted_on_stamps_the_request_time(
    action_env: ActionEnv, code: str
) -> None:
    """지난 수행일로 이전 Next Action을 닫으면 종료일은 오늘이고 수정·이력 시각은 요청 시각이다.

    테스트 코드: AC-101
    """
    # given: KIM의 기준 행(Open)이 11-05 10:00에 등록돼 있다
    basis = await _given_action(action_env, code, _at(5))

    # when: 수행일 11-10으로 그 id를 닫으며 등록한다 (전제: 서버 시계 T)
    created = await action_env.act(
        KIM, code=code, advance=0, acted_on=date(2026, 11, 10), close_previous=basis.id
    )

    # then: 기준 행의 종료일은 오늘(11-13, 수행일 11-10이 아님)이고 수정 시각은 T다
    closed = await action_env.stored(basis.id)
    assert closed.next_action_state == NextActionState(NextActionStatus.DONE, closed_on=TODAY)
    assert closed.updated_at == T
    # then: 종료 이력과 등록 이력의 시각은 T이고 새 Action의 수행일은 11-10이다
    newest = (await action_env.entries(code))[-2:]
    assert {e.changed_at for e in newest} == {T}
    assert "종료(수행)" in {e.draft.after for e in newest}
    assert (await action_env.stored(created.id)).acted_on == PAST


async def test_status_change_with_a_past_acted_on_uses_the_request_time(
    action_env: ActionEnv, code: str
) -> None:
    """지난 수행일로 Status를 바꾸며 등록하면 스냅숏·진입일·수정·이력 시각은 요청 시점 기준이다.

    테스트 코드: AC-102
    """
    # when: 수행일 11-10으로 Status를 제품소개로 바꾸며 등록한다 (전제: 서버 시계 T)
    created = await action_env.act(
        KIM,
        code=code,
        advance=0,
        acted_on=date(2026, 11, 10),
        status_changes=(StatusChangeInput(field="status_key", value="introduction"),),
    )

    # then: 스냅숏은 제품소개이고 수행일은 11-10이다
    stored = await action_env.stored(created.id)
    assert stored.snapshot.status_key == "introduction"
    assert stored.acted_on == PAST
    # then: Deal의 Status 진입일은 오늘(11-13)이고 수정 시각은 T다
    from app.domain.deal.code import DealCode  # noqa: PLC0415

    deal = await action_env.env.uow.deals.get(DealCode(code))
    assert deal.status_changed_on == TODAY
    assert deal.updated_at == T
    # then: 새로 남은 이력(Status 변경·Action 등록)의 시각은 모두 T다
    entries = await action_env.entries(code)
    assert {e.changed_at for e in entries if str(e.draft.category) != "created"} == {T}


async def test_editing_and_next_action_status_change_keep_the_acted_on(
    action_env: ActionEnv, code: str
) -> None:
    """수정과 Next Action 상태 변경은 수행일을 바꾸지 않는다.

    테스트 코드: AC-103
    """
    # given: 수행일이 11-10인 KIM의 Action
    action = await action_env.act(KIM, code=code, advance=0, acted_on=date(2026, 11, 10))
    assert action.acted_on == PAST

    # when: 진행사항만 고친다
    await action_env.update_as(action.id, KIM, action="고친 진행사항")
    # then: 수행일은 그대로다
    assert (await action_env.stored(action.id)).acted_on == PAST

    # when: Next Action 상태를 종료(수행)로 바꾼다
    await action_env.set_status(action.id, KIM, "done")
    # then: 수행일은 그대로다
    assert (await action_env.stored(action.id)).acted_on == PAST


async def test_another_requester_with_a_past_acted_on_is_recorded_as_that_requester(
    action_env: ActionEnv, code: str
) -> None:
    """수행일을 지정해도 담당자는 요청자다.

    테스트 코드: AC-092
    """
    # when: PARK이 지난 수행일로 등록한다
    action = await action_env.act(PARK, code=code, advance=0, acted_on=date(2026, 11, 10))

    # then: 담당자는 PARK이다
    assert (await action_env.stored(action.id)).actor_user_id == PARK.user_id
