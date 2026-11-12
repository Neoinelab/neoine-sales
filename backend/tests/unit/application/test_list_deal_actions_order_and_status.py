"""ListDealActions: 정렬 10종의 동률·빈 값 규칙, Next Action 상태 필터, 퇴사한 작성자."""

from datetime import date
from typing import TYPE_CHECKING

from app.application.deal.inputs import Actor
from app.application.ports.deal_action_repository import (
    DealActionQuery,
    DealActionSort,
    NextActionStatusFilter,
)
from app.domain.auth.principal import Role
from tests.factories_auth import make_user
from tests.support.user_ids import uid
from tests.unit.application.action_env import KIM, PARK

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv


async def _names(action_env: ActionEnv, **criteria: object) -> list[str]:
    query = DealActionQuery(deal_code=action_env.deal.item.deal.id, **criteria)  # type: ignore[arg-type]
    return [str(a.content.action) for a in await action_env.list.execute(query)]


async def _given_status_actions(action_env: ActionEnv) -> None:
    """오래된 순서로 열림(Open)·수행(종료 수행)·미수행(종료 미수행)·진행만(Next Action 없음)."""
    await action_env.act(KIM, action="열림")
    done = await action_env.act(KIM, action="수행")
    await action_env.set_status(done.id, KIM, "done")
    not_done = await action_env.act(KIM, action="미수행")
    await action_env.set_status(not_done.id, KIM, "not_done")
    await action_env.act(KIM, action="진행만", next_action="")


async def test_resigned_actor_is_found_by_user_id_and_unknown_user_lists_nothing(
    action_env: ActionEnv,
) -> None:
    """담당자 조건은 퇴사한 작성자의 Action도 찾고 없는 사용자는 0건이다.

    테스트 코드: NA-025
    """
    # given: 퇴사 처리된 사용자가 작성한 Action
    leaver = Actor(user_id=uid("leaver"), role=Role.SALES)
    users = action_env.env.uow.users
    user = make_user("leaver", entity_id=leaver.user_id)
    await users.add(user)
    await action_env.act(leaver, action="퇴사자 활동")
    await action_env.act(KIM, action="재직자 활동")
    user.resign(action_env.env.clock.now())
    await users.update(user)
    # when: 그 사용자 id로 조회한다
    by_leaver = await _names(action_env, actor_user_id=leaver.user_id)
    # then: 그 Action이다
    assert by_leaver == ["퇴사자 활동"]
    # when: 없는 사용자 id로 조회한다
    by_unknown = await _names(action_env, actor_user_id=uid("nobody"))
    # then: 0건이다
    assert by_unknown == []


async def test_status_filter_picks_one_status_closed_means_both_and_excludes_no_next_action(
    action_env: ActionEnv,
) -> None:
    """상태 필터는 그 상태만 고르고 closed는 종료 둘 다이며 Next Action 없는 Action은 빠진다.

    테스트 코드: NA-033
    """
    # given: 열림·수행·미수행·진행만 Action
    await _given_status_actions(action_env)
    # when: next_action_status를 open, done, not_done, closed로 각각 조회한다
    opened = await _names(action_env, next_action_status=NextActionStatusFilter.OPEN)
    done = await _names(action_env, next_action_status=NextActionStatusFilter.DONE)
    not_done = await _names(action_env, next_action_status=NextActionStatusFilter.NOT_DONE)
    closed = await _names(action_env, next_action_status=NextActionStatusFilter.CLOSED)
    # then: 각각 그 상태만이고 closed는 종료 둘 다이며 진행만은 어디에도 없다
    assert opened == ["열림"]
    assert done == ["수행"]
    assert not_done == ["미수행"]
    assert closed == ["미수행", "수행"]


async def test_without_a_status_filter_every_action_is_listed_including_no_next_action(
    action_env: ActionEnv,
) -> None:
    """상태 필터가 없으면 진행사항만 Action도 나온다.

    테스트 코드: NA-033
    """
    # given: 열림·수행·미수행·진행만 Action
    await _given_status_actions(action_env)
    # when: 상태 필터 없이 조회한다
    names = await _names(action_env)
    # then: 네 건이 최신순으로 나온다
    assert names == ["진행만", "미수행", "수행", "열림"]


async def test_status_filter_combines_with_other_conditions_and_reopened_is_open(
    action_env: ActionEnv,
) -> None:
    """상태 필터는 다른 조건과 AND이고 Open으로 되돌린 Action은 open에 나온다.

    테스트 코드: NA-034
    """
    # given: NA-033의 Action들과 종료했다가 Open으로 되돌린 "되돌림"
    await _given_status_actions(action_env)
    reopened = await action_env.act(KIM, action="되돌림")
    await action_env.set_status(reopened.id, KIM, "done")
    await action_env.set_status(reopened.id, KIM, "open")
    # when: closed + 검색어 "미수행"으로 조회한다
    closed_and_keyword = await _names(
        action_env, next_action_status=NextActionStatusFilter.CLOSED, keyword="미수행"
    )
    # then: "미수행"만 나온다
    assert closed_and_keyword == ["미수행"]
    # when: open으로 조회한다
    opened = await _names(action_env, next_action_status=NextActionStatusFilter.OPEN)
    # then: "되돌림"을 포함한 Open 행이다
    assert opened == ["되돌림", "열림"]
    # when: closed로 조회한다
    closed = await _names(action_env, next_action_status=NextActionStatusFilter.CLOSED)
    # then: "되돌림"이 없는 종료 행이다
    assert closed == ["미수행", "수행"]


async def test_acted_at_ties_list_the_earlier_registered_action_first_in_both_directions(
    action_env: ActionEnv,
) -> None:
    """수행일시 정렬은 같은 시각이면 어느 방향이든 먼저 등록한 Action이 앞이다.

    테스트 코드: NA-038
    """
    # given: 같은 수행 일시의 "먼저 등록"·"나중 등록"과 그 뒤의 "셋째"
    await action_env.act(KIM, action="먼저 등록")
    await action_env.act(KIM, action="나중 등록", advance=0)
    await action_env.act(KIM, action="셋째")
    # when: acted_at_desc로 조회한다
    desc = await _names(action_env, sort=DealActionSort.ACTED_AT_DESC)
    # then: 셋째, 먼저 등록, 나중 등록 순이다
    assert desc == ["셋째", "먼저 등록", "나중 등록"]
    # when: acted_at_asc로 조회한다
    asc = await _names(action_env, sort=DealActionSort.ACTED_AT_ASC)
    # then: 먼저 등록, 나중 등록, 셋째 순이다
    assert asc == ["먼저 등록", "나중 등록", "셋째"]


async def test_due_date_sort_puts_actions_without_due_last_in_both_directions(
    action_env: ActionEnv,
) -> None:
    """Due Date 정렬은 Due가 없는 Action을 방향과 관계없이 맨 뒤에 두고 동률은 최신 수행이 먼저다.

    테스트 코드: NA-039
    """
    # given: Due 3/1 "늦은 기한", Due 2/1 "빠른 기한 먼저"·"빠른 기한 나중", 진행사항만 "기한 없음"
    await action_env.act(KIM, action="늦은 기한", due_date=date(2026, 3, 1))
    await action_env.act(KIM, action="빠른 기한 먼저", due_date=date(2026, 2, 1))
    await action_env.act(KIM, action="빠른 기한 나중", due_date=date(2026, 2, 1))
    await action_env.act(KIM, action="기한 없음", next_action="")
    # when: due_date_asc로 조회한다
    asc = await _names(action_env, sort=DealActionSort.DUE_DATE_ASC)
    # then: 빠른 기한 나중, 먼저, 늦은 기한, 기한 없음 순이다
    assert asc == ["빠른 기한 나중", "빠른 기한 먼저", "늦은 기한", "기한 없음"]
    # when: due_date_desc로 조회한다
    desc = await _names(action_env, sort=DealActionSort.DUE_DATE_DESC)
    # then: 늦은 기한, 빠른 기한 나중, 먼저, 기한 없음 순이다(동률은 최신 수행이 먼저)
    assert desc == ["늦은 기한", "빠른 기한 나중", "빠른 기한 먼저", "기한 없음"]


async def test_actor_sort_compares_display_name_or_login_id_ignoring_case(
    action_env: ActionEnv,
) -> None:
    """담당자 정렬은 표시 이름(없으면 로그인 아이디)을 대소문자 구분 없이 비교한다.

    테스트 코드: NA-040
    """
    # given: 표시 이름 "박영업"·"김영업"의 Action과 표시 이름이 빈 로그인 아이디 "Lee"의 Action
    users = action_env.env.uow.users
    for actor, name in ((PARK, "박영업"), (KIM, "김영업")):
        user = await users.get(actor.user_id)
        user.display_name = name
        await users.update(user)
    lee = Actor(user_id=uid("Lee"), role=Role.SALES)
    await users.add(make_user("Lee", entity_id=lee.user_id))
    await action_env.act(PARK, action="박 활동")
    await action_env.act(KIM, action="김 활동")
    await action_env.act(lee, action="리 활동")
    # when: actor_asc로 조회한다
    asc = await _names(action_env, sort=DealActionSort.ACTOR_ASC)
    # then: "lee" < "김영업" < "박영업" 순이다
    assert asc == ["리 활동", "김 활동", "박 활동"]
    # when: actor_desc로 조회한다
    desc = await _names(action_env, sort=DealActionSort.ACTOR_DESC)
    # then: 반대 순이다
    assert desc == ["박 활동", "김 활동", "리 활동"]


async def test_action_type_sort_compares_the_current_type_name_ignoring_case(
    action_env: ActionEnv,
) -> None:
    """유형 정렬은 지금 유형 이름을 대소문자 구분 없이 코드 포인트 순으로 비교한다.

    테스트 코드: NA-041
    """
    # given: 유형 "이메일"·"미팅"·"Demo"의 Action
    await action_env.act(KIM, action="메일", action_type="이메일")
    await action_env.act(KIM, action="회의", action_type="미팅")
    await action_env.act(KIM, action="시연", action_type="Demo")
    # when: action_type_asc로 조회한다
    asc = await _names(action_env, sort=DealActionSort.ACTION_TYPE_ASC)
    # then: "demo" < "미팅" < "이메일" 순이다
    assert asc == ["시연", "회의", "메일"]
    # when: action_type_desc로 조회한다
    desc = await _names(action_env, sort=DealActionSort.ACTION_TYPE_DESC)
    # then: 반대 순이다
    assert desc == ["메일", "회의", "시연"]


async def test_status_sort_orders_open_done_not_done_and_puts_no_status_last(
    action_env: ActionEnv,
) -> None:
    """상태 정렬은 Open·종료(수행)·종료(미수행) 순이고 상태 없음은 방향과 관계없이 맨 뒤다.

    테스트 코드: NA-042
    """
    # given: 열림·수행·미수행·진행만 Action
    await _given_status_actions(action_env)
    # when: next_action_status_asc로 조회한다
    asc = await _names(action_env, sort=DealActionSort.NEXT_ACTION_STATUS_ASC)
    # then: 열림, 수행, 미수행, 진행만 순이다
    assert asc == ["열림", "수행", "미수행", "진행만"]
    # when: next_action_status_desc로 조회한다
    desc = await _names(action_env, sort=DealActionSort.NEXT_ACTION_STATUS_DESC)
    # then: 미수행, 수행, 열림, 진행만 순이다
    assert desc == ["미수행", "수행", "열림", "진행만"]
