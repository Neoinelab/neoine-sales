"""ListDealActions: Deal 단위 전부 반환, 필터는 AND, 날짜는 로컬 업무 날짜 양끝 포함."""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_action_repository import DealActionQuery, DealActionSort
from app.domain.action_type.values import ActionTypeId
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from tests.factories_action_type import type_id
from tests.support.ids import new_id
from tests.support.user_ids import uid
from tests.support.user_seed import ensure_users
from tests.unit.application.action_env import BOSS, KIM, PARK

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.unit.application.action_env import ActionEnv


async def _names(action_env: ActionEnv, **criteria: object) -> list[str]:
    query = DealActionQuery(deal_code=action_env.deal.item.deal.id, **criteria)  # type: ignore[arg-type]
    found = await action_env.list.execute(query)
    assert all(a.content.action is not None for a in found)
    return [str(a.content.action) for a in found]


async def test_list_actions_of_missing_deal_is_not_found(action_env: ActionEnv) -> None:
    """없는 Deal의 Action 목록은 DealNotFoundError다.

    테스트 코드: NA-021
    """
    # given: 존재하지 않는 Deal code의 조회 조건
    query = DealActionQuery(deal_code=DealCode("20261016-ZZZZ"))
    # when·then: 목록을 조회하면 Deal을 찾을 수 없다는 오류다
    with pytest.raises(DealNotFoundError):
        await action_env.list.execute(query)


async def test_list_returns_every_action_of_the_deal_without_paging(action_env: ActionEnv) -> None:
    """조건이 없으면 Action 전부가 페이지 없이 수행일 최신순(같은 날은 나중 등록 먼저)으로 나온다.

    테스트 코드: NA-019
    """
    # given: 한 Deal에 Action 25건이 차례로 있다
    for number in range(25):
        await action_env.act(KIM, action=f"활동 {number:02d}")
    # when: 조건 없이 목록을 조회한다
    names = await _names(action_env)
    # then: 25건 전부가 최신 수행 순으로 온다
    assert names == [f"활동 {number:02d}" for number in reversed(range(25))]


async def test_list_excludes_the_actions_of_other_deals(action_env: ActionEnv) -> None:
    """다른 Deal의 Action은 목록에 나오지 않는다.

    테스트 코드: NA-020
    """
    # given: Deal A에 "내 Deal", Deal B에 "다른 Deal" Action이 있다
    other = await action_env.env.new_deal()
    await action_env.act(KIM, action="내 Deal")
    await action_env.act(KIM, code=other.item.deal.id.value, action="다른 Deal")
    # when: Deal A의 목록을 조회한다
    names = await _names(action_env)
    # then: Deal A의 Action만 나온다
    assert names == ["내 Deal"]


async def test_default_sort_is_latest_acted_on_first_and_ascending_is_available(
    action_env: ActionEnv,
) -> None:
    """정렬을 주지 않으면 최신 수행(수행일, 같은 날은 id)이 먼저이고 acted_at_asc는 반대 순서다.

    테스트 코드: NA-019, NA-038
    """
    # given: 차례로 등록한 Action 세 건
    for name in ("첫째", "둘째", "셋째"):
        await action_env.act(KIM, action=name)
    # when: 정렬 없이, acted_at_desc, acted_at_asc로 조회한다
    default = await _names(action_env)
    desc = await _names(action_env, sort=DealActionSort.ACTED_AT_DESC)
    asc = await _names(action_env, sort=DealActionSort.ACTED_AT_ASC)
    # then: 기본과 desc는 최신순, asc는 오래된 순이다
    assert default == ["셋째", "둘째", "첫째"]
    assert desc == ["셋째", "둘째", "첫째"]
    assert asc == ["첫째", "둘째", "셋째"]


async def test_sort_by_due_date_breaks_ties_by_latest_acted_on(action_env: ActionEnv) -> None:
    """Due Date 정렬에서 Due가 같으면 최신 수행(수행일, 같은 날은 id 큰 것)이 먼저다.

    테스트 코드: NA-039
    """
    # given: Due 3/1 "늦은 기한", Due 2/1 "빠른 기한 먼저"와 나중에 수행한 "빠른 기한 나중"
    await action_env.act(KIM, action="늦은 기한", due_date=date(2026, 3, 1))
    await action_env.act(KIM, action="빠른 기한 먼저", due_date=date(2026, 2, 1))
    await action_env.act(KIM, action="빠른 기한 나중", due_date=date(2026, 2, 1))
    # when: due_date_asc로 조회한다
    names = await _names(action_env, sort=DealActionSort.DUE_DATE_ASC)
    # then: Due 오름차순이고 같은 Due는 최신 수행이 먼저다
    assert names == ["빠른 기한 나중", "빠른 기한 먼저", "늦은 기한"]


async def test_list_filters_combine_with_and(action_env: ActionEnv) -> None:
    """유형·담당자·검색어 조건은 AND로 결합된다.

    테스트 코드: NA-023
    """
    # given: kim의 "킥오프"(미팅), park의 "견적 발송"(이메일)과 "최종 미팅"(미팅)
    await action_env.act(KIM, action="킥오프", action_type="미팅")
    await action_env.act(PARK, action="견적 발송", action_type="이메일")
    await action_env.act(PARK, action="최종 미팅", action_type="미팅")
    meeting = type_id("미팅")
    # when: 유형 미팅 + 담당자 park으로 조회한다
    by_type_and_actor = await _names(action_env, action_type_id=meeting, actor_user_id=uid("park"))
    # then: "최종 미팅"만 나온다
    assert by_type_and_actor == ["최종 미팅"]
    # when: 담당자 park + 검색어 "견적"으로 조회한다
    by_actor_and_keyword = await _names(action_env, actor_user_id=uid("park"), keyword="견적")
    # then: "견적 발송"만 나온다
    assert by_actor_and_keyword == ["견적 발송"]
    # when: Action이 없는 담당자 admin으로 조회한다
    by_idle_actor = await _names(action_env, actor_user_id=BOSS.user_id)
    # then: 0건이다
    assert by_idle_actor == []


async def test_filters_by_action_type_id(action_env: ActionEnv) -> None:
    """유형 id로 거르면 그 유형의 Action만 나온다.

    테스트 코드: NA-024
    """
    # given: 통화 유형과 데모 유형의 Action
    await action_env.act(KIM, action="통화 기록", action_type="통화")
    await action_env.act(KIM, action="데모 기록", action_type="데모")
    # when: 데모 유형 id와 통화 유형 id로 각각 조회한다
    demo = await _names(action_env, action_type_id=type_id("데모"))
    call = await _names(action_env, action_type_id=type_id("통화"))
    # then: 각 유형의 Action만 나온다
    assert demo == ["데모 기록"]
    assert call == ["통화 기록"]


async def test_unknown_type_id_lists_nothing(action_env: ActionEnv) -> None:
    """없는 유형 id는 오류 없이 0건이다.

    테스트 코드: NA-024
    """
    # given: 통화 유형의 Action
    await action_env.act(KIM, action="통화 기록", action_type="통화")
    # when: 없는 유형 id로 조회한다
    names = await _names(action_env, action_type_id=new_id())
    # then: 오류 없이 0건이다
    assert names == []


async def test_the_listed_action_carries_the_current_type_name(action_env: ActionEnv) -> None:
    """유형 이름을 바꿔도 같은 id로 같은 Action이 나오고 응답 유형 이름은 지금 이름이다.

    테스트 코드: NA-024
    """
    # given: 유형 "통화"의 Action이 있고 유형 이름을 "전화"로 바꿨다
    await action_env.act(KIM, action="통화 기록", action_type="통화")
    renamed = await action_env.env.uow.action_types.get(ActionTypeId(type_id("통화")))
    renamed.rename("전화", action_env.env.clock.now())
    await action_env.env.uow.action_types.update(renamed)
    # when: 같은 유형 id로 조회한다
    query = DealActionQuery(
        deal_code=action_env.deal.item.deal.id, action_type_id=ActionTypeId(type_id("통화"))
    )
    (listed,) = await action_env.list.execute(query)
    # then: 같은 Action이 나오고 유형 이름은 지금 이름이다
    assert listed.content.action == "통화 기록"
    assert listed.content.action_type.name == "전화"


async def test_keyword_matches_the_texts_and_action_comments_ignoring_case_and_wildcards(
    action_env: ActionEnv,
) -> None:
    """검색어는 진행사항·Next Action·그 Action의 Comment 본문에서 대소문자 구분 없이 부분 일치하고
    %·_는 글자 그대로다. Deal Comment는 찾지 않는다.

    테스트 코드: NA-026, NA-027, CM-040
    """
    # given: 진행사항 "Kickoff"·Next Action "견적서 준비"·Action Comment "예산 100%"인 Action,
    # given: Next Action "CONTRACT 초안"인 Action, Comment 없는 Action, Deal Comment "특이사항 메모"
    from tests.factories_comment import make_comment  # noqa: PLC0415

    first = await action_env.act(KIM, action="Kickoff", next_action="견적서 준비")
    await action_env.act(KIM, action="제안", next_action="CONTRACT 초안")
    await action_env.act(KIM, action="회의", next_action="")
    comments = action_env.env.uow.deal_comments
    code = first.deal_code
    await comments.add(
        make_comment(deal_code=code, action_id=first.id, body="예산 100%", author=KIM.user_id)
    )
    await comments.add(make_comment(deal_code=code, body="특이사항 메모", author=KIM.user_id))
    # when: Action Comment 본문의 말 "예산"과 "예산 100%"로 조회한다
    by_comment = await _names(action_env, keyword="예산")
    by_comment_phrase = await _names(action_env, keyword="예산 100%")
    # then: Comment가 있는 Action만 나온다
    assert by_comment == ["Kickoff"]
    assert by_comment_phrase == ["Kickoff"]
    # when: Deal Comment에만 있는 말로 조회한다
    by_deal_comment = await _names(action_env, keyword="특이사항")
    # then: 연결된 Action이 없으므로 같은 Deal의 어느 Action도 나오지 않는다
    assert by_deal_comment == []
    # when: 검색어 "kickoff"로 조회한다
    by_progress = await _names(action_env, keyword="kickoff")
    # then: 진행사항이 맞은 첫 Action이다
    assert by_progress == ["Kickoff"]
    # when: 검색어 "contract"(Next Action, 대소문자 다름)로 조회한다
    by_next_action = await _names(action_env, keyword="contract")
    # then: 두 번째 Action이다
    assert by_next_action == ["제안"]
    # when: 검색어 "준비", "100%", "_"로 조회한다
    by_prepare = await _names(action_env, keyword="준비")
    by_percent = await _names(action_env, keyword="100%")
    by_underscore = await _names(action_env, keyword="_")
    # then: Next Action·Comment 일치는 찾고 `_`는 와일드카드가 아니라 0건이다
    assert by_prepare == ["Kickoff"]
    assert by_percent == ["Kickoff"]
    assert by_underscore == []


async def test_keyword_is_trimmed_and_blank_keyword_means_no_condition(
    action_env: ActionEnv,
) -> None:
    """검색어 앞뒤 공백은 무시하고 공백뿐이면 조건이 없는 것과 같다.

    테스트 코드: NA-027
    """
    # given: "견적 발송"과 "킥오프" Action
    await action_env.act(KIM, action="견적 발송")
    await action_env.act(KIM, action="킥오프")
    # when: 검색어 "  견적  "과 "   "로 조회한다
    padded = await _names(action_env, keyword="  견적  ")
    blank = await _names(action_env, keyword="   ")
    # then: 앞은 "견적 발송"만, 뒤는 전체다
    assert padded == ["견적 발송"]
    assert blank == ["킥오프", "견적 발송"]


async def test_due_range_is_inclusive_on_both_ends(action_env: ActionEnv) -> None:
    """Due Date 범위는 양끝을 포함하고 Due Date가 없는 Action은 빠진다.

    테스트 코드: NA-030
    """
    # given: Due 4/1, 4/10인 Action과 Due가 없는 진행사항만 Action
    await action_env.act(KIM, action="a", due_date=date(2026, 4, 1))
    await action_env.act(KIM, action="b", due_date=date(2026, 4, 10))
    await action_env.act(KIM, action="진행만", next_action="")
    # when: 4/1~4/1로 조회한다
    first_day = await _names(action_env, due_from=date(2026, 4, 1), due_to=date(2026, 4, 1))
    # then: 4/1 Action만 나온다
    assert first_day == ["a"]
    # when: 시작 4/10만 주고 조회한다
    from_last = await _names(action_env, due_from=date(2026, 4, 10))
    # then: 4/10 Action만 나오고 Due 없는 Action은 없다
    assert from_last == ["b"]
    # when: 4/2~4/9로 조회한다
    inside = await _names(action_env, due_from=date(2026, 4, 2), due_to=date(2026, 4, 9))
    # then: 0건이다
    assert inside == []
    # when: 끝 3/31만 주고 조회한다
    before = await _names(action_env, due_to=date(2026, 3, 31))
    # then: 0건이다(Due 없는 Action도 없다)
    assert before == []


async def test_acted_date_range_covers_whole_local_days_on_both_ends(
    action_env: ActionEnv, local_tz: Callable[[str], None]
) -> None:
    """수행일 조건은 수행일을 양끝 포함으로 비교하고 요청 시각의 업무 날짜가 수행일이 된다.

    테스트 코드: NA-029
    """
    # given: 서버 시간대 Asia/Seoul, 전날 23:59·당일 00:00·당일 23:59·다음날 00:00의 Action
    local_tz("Asia/Seoul")
    moments = {  # 로컬(KST) 시각 -> UTC
        "전날 23:59": datetime(2026, 10, 15, 14, 59, tzinfo=UTC),
        "당일 00:00": datetime(2026, 10, 15, 15, 0, tzinfo=UTC),
        "당일 23:59": datetime(2026, 10, 16, 14, 59, tzinfo=UTC),
        "다음날 00:00": datetime(2026, 10, 16, 15, 0, tzinfo=UTC),
    }
    for name, moment in moments.items():
        action_env.set_clock(moment)
        await action_env.act(KIM, action=name, advance=0)
    # when: acted_from=acted_to=당일로 조회한다
    on_the_day = await _names(
        action_env, acted_from=date(2026, 10, 16), acted_to=date(2026, 10, 16)
    )
    # then: 당일의 두 건이다
    assert sorted(on_the_day) == ["당일 00:00", "당일 23:59"]
    # when: acted_from만 당일로 조회한다
    from_the_day = await _names(action_env, acted_from=date(2026, 10, 16))
    # then: 당일 이후 세 건이다
    assert sorted(from_the_day) == ["다음날 00:00", "당일 00:00", "당일 23:59"]
    # when: acted_to만 전날로 조회한다
    until_before = await _names(action_env, acted_to=date(2026, 10, 15))
    # then: 전날까지의 한 건이다
    assert until_before == ["전날 23:59"]


async def test_list_passes_the_requested_sort_to_the_repository(action_env: ActionEnv) -> None:
    """담당자 정렬을 요청하면 로그인 아이디 순으로 양방향 정렬된다."""
    # given: 로그인 아이디 kim·park 사용자의 Action
    await ensure_users(action_env.env.uow.users, KIM.user_id, PARK.user_id)
    await action_env.act(PARK, action="박 먼저")
    await action_env.act(KIM, action="김 나중")
    # when: actor_asc, actor_desc로 조회한다
    asc = await _names(action_env, sort=DealActionSort.ACTOR_ASC)
    desc = await _names(action_env, sort=DealActionSort.ACTOR_DESC)
    # then: 아이디 오름차순과 그 반대다
    assert asc == ["김 나중", "박 먼저"]
    assert desc == ["박 먼저", "김 나중"]
