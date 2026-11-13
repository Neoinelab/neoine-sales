"""DealActionRepository 검색 계약(필터·정렬·날짜·전부 반환): Fake와 SQL 구현에 같은 테스트."""

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from app.application.ports.deal_action_repository import DealActionSort
from tests.factories import NOW, make_deal_action, make_deal_code
from tests.factories_action_type import make_action_type
from tests.support.ids import new_id
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.unit.repositories.deal_action_case import Case


async def _seed(action_case: Case) -> None:
    rows = [
        ("통화", "첫 통화", "견적서 준비", "예산 문의 100%", "kim", 0, date(2026, 2, 10)),
        ("미팅", "킥오프 미팅", "요구사항 정리", "일정", "park", 1, date(2026, 2, 1)),
        ("미팅", "최종 미팅", "계약서 초안", "조건", "kim", 2, date(2026, 2, 10)),
    ]
    for action_type, action, next_action, memo, actor, day, due in rows:
        await action_case.add(
            make_deal_action(
                now=NOW + timedelta(days=day),
                action_type=action_type,
                action=action,
                next_action=next_action,
                memo=memo,
                actor_user_id=uid(actor),
                due_date=due,
            )
        )


async def _type_id(action_case: Case, name: str) -> object:
    return next(t.id for t in await action_case.action_types.list() if t.name == name)


async def test_search_orders_by_latest_acted_on_first_by_default(action_case: Case) -> None:
    """정렬을 지정하지 않으면 수행일이 최신인 것부터 나온다.

    테스트 코드: AC-115
    """
    # given: 수행일이 다른 Action 3건
    await _seed(action_case)

    # when: 정렬 없이 검색한다
    by_default = await action_case.search()
    # then: 수행일 최신순이다
    assert by_default == ["최종 미팅", "킥오프 미팅", "첫 통화"]
    # when: 수행일 내림차순으로 검색한다
    descending = await action_case.search(sort=DealActionSort.ACTED_AT_DESC)
    # then: 기본 정렬과 같다
    assert descending == [
        "최종 미팅",
        "킥오프 미팅",
        "첫 통화",
    ]


async def test_search_can_order_by_oldest_acted_on_first(action_case: Case) -> None:
    """수행일 오름차순으로 검색하면 오래된 것부터 나온다."""
    # given: 수행일이 다른 Action 3건
    await _seed(action_case)

    # when: 수행일 오름차순으로 검색한다
    found = await action_case.search(sort=DealActionSort.ACTED_AT_ASC)
    # then: 오래된 것부터 나온다
    assert found == [
        "첫 통화",
        "킥오프 미팅",
        "최종 미팅",
    ]


async def test_actions_with_the_same_acted_on_follow_the_id_in_the_sort_direction(
    action_case: Case,
) -> None:
    """수행일이 같으면 id가 방향을 따른다: 오름차순은 먼저 등록한 것이, 내림차순은 나중 것이 앞이다.

    테스트 코드: AC-115
    """
    # given: 수행일이 같은 Action 3건을 차례로 등록(시각이 거꾸로 흘러도 id가 순서다)
    for number, name in enumerate(("첫째", "둘째", "셋째")):
        await action_case.add(make_deal_action(NOW - timedelta(minutes=number), action=name))

    # when: 오름차순으로 검색한다
    ascending = await action_case.search(sort=DealActionSort.ACTED_AT_ASC)
    # then: 등록 순서대로 나온다
    assert ascending == ["첫째", "둘째", "셋째"]
    # when: 내림차순으로 검색한다
    descending = await action_case.search(sort=DealActionSort.ACTED_AT_DESC)
    # then: 반대로 나중에 등록한 것이 앞이다
    assert descending == ["셋째", "둘째", "첫째"]


async def test_search_by_due_date_breaks_ties_by_latest_acted_on(action_case: Case) -> None:
    """기한 오름차순에서 기한이 같으면 수행일 최신순으로 나온다."""
    # given: 기한이 같은 Action이 둘 있는 3건
    await _seed(action_case)

    # 기한 02-01 -> 킥오프, 02-10 동률은 수행일 최신순: 최종 -> 첫 통화
    # when: 기한 오름차순으로 검색한다
    found = await action_case.search(sort=DealActionSort.DUE_DATE_ASC)
    # then: 기한이 빠른 것이 먼저고, 동률은 수행일 최신순이다
    assert found == [
        "킥오프 미팅",
        "최종 미팅",
        "첫 통화",
    ]


async def test_search_filters_combine_with_and(action_case: Case) -> None:
    """유형·수행자 필터는 AND로 결합된다."""
    # given: 수행자와 유형이 다른 Action 3건
    await _seed(action_case)

    meeting = await _type_id(action_case, "미팅")
    # when: 유형과 수행자를 함께 걸어 검색한다
    both = await action_case.search(action_type_id=meeting, actor_user_id=uid("kim"))
    # then: 둘 다 맞는 것만 나온다
    assert both == ["최종 미팅"]
    # when: 수행자만 걸어 검색한다
    one_actor = await action_case.search(actor_user_id=uid("park"))
    # then: 그 수행자의 것만 나온다
    assert one_actor == ["킥오프 미팅"]
    # when: 없는 수행자로 검색한다
    nobody = await action_case.search(actor_user_id=uid("nobody"))
    # then: 결과가 없다
    assert nobody == []


async def test_search_keyword_matches_the_three_text_fields_ignoring_case(
    action_case: Case,
) -> None:
    """키워드는 진행사항·Next Action·Memo에서 대소문자 무시로 찾는다."""
    # given: 세 텍스트 필드에 서로 다른 말이 있는 Action들과 영문 Action 하나
    await _seed(action_case)
    await action_case.add(make_deal_action(NOW + timedelta(days=9), action="Kickoff Memo"))

    # when: 진행사항에 있는 말로 검색한다
    by_action = await action_case.search(keyword="킥오프")
    # then: 그 Action이 나온다
    assert by_action == ["킥오프 미팅"]  # action
    # when: Next Action에 있는 말로 검색한다
    by_next_action = await action_case.search(keyword="계약서")
    # then: 그 Action이 나온다
    assert by_next_action == ["최종 미팅"]  # next_action
    # when: Memo에 있는 말로 검색한다
    by_memo = await action_case.search(keyword="예산")
    # then: 그 Action이 나온다
    assert by_memo == ["첫 통화"]  # memo
    # when: 대문자로 검색한다
    upper = await action_case.search(keyword="KICKOFF")
    # then: 소문자 Action이 나온다
    assert upper == ["Kickoff Memo"]
    # when: 소문자로 검색한다
    lower = await action_case.search(keyword="kickoff")
    # then: 같은 Action이 나온다
    assert lower == ["Kickoff Memo"]


async def test_search_keyword_treats_wildcards_literally(action_case: Case) -> None:
    """키워드의 % 와 _ 는 와일드카드가 아니라 글자 그대로 찾는다."""
    # given: Memo에 "100%"가 있는 Action이 포함된 3건
    await _seed(action_case)

    # when: "100%"로 검색한다
    percent_phrase = await action_case.search(keyword="100%")
    # then: 그 Action만 나온다
    assert percent_phrase == ["첫 통화"]
    # when: "%" 하나로 검색한다
    percent = await action_case.search(keyword="%")
    # then: 글자 %가 있는 Action만 나온다
    assert percent == ["첫 통화"]
    # when: "_" 하나로 검색한다
    underscore = await action_case.search(keyword="_")
    # then: 결과가 없다
    assert underscore == []


async def test_search_keyword_finds_text_deep_inside_a_very_long_memo(action_case: Case) -> None:
    """아주 긴 Memo의 깊은 곳에 있는 말도 키워드로 찾는다."""
    # given: 20,000자 가까운 Memo의 중간에 키워드가 있는 Action
    long_memo = "가" * 15_000 + "깊은키워드" + "나" * 5_000
    await action_case.add(make_deal_action(NOW, action="긴 메모", memo=long_memo))

    # when: 그 키워드로 검색한다
    found = await action_case.search(keyword="깊은키워드")
    # then: 그 Action이 나온다
    assert found == ["긴 메모"]


async def test_search_due_range_is_inclusive_on_both_ends(action_case: Case) -> None:
    """Due 범위는 시작일과 종료일을 모두 포함한다."""
    # given: 기한이 2월 1일·10일인 Action 3건
    await _seed(action_case)

    # when: 시작일과 종료일을 모두 걸어 검색한다
    both = await action_case.search(due_from=date(2026, 2, 1), due_to=date(2026, 2, 10))
    # then: 양 끝 날짜 Action이 모두 나온다
    assert both == [
        "최종 미팅",
        "킥오프 미팅",
        "첫 통화",
    ]
    # when: 시작일만 걸어 검색한다
    from_only = await action_case.search(due_from=date(2026, 2, 10))
    # then: 그날 이후 Action이 나온다
    assert from_only == ["최종 미팅", "첫 통화"]
    # when: 종료일만 걸어 검색한다
    to_only = await action_case.search(due_to=date(2026, 2, 1))
    # then: 그날 이전 Action이 나온다
    assert to_only == ["킥오프 미팅"]
    # when: 모든 기한보다 늦은 시작일로 검색한다
    after_all = await action_case.search(due_from=date(2026, 2, 11))
    # then: 결과가 없다
    assert after_all == []


async def test_search_acted_date_covers_the_local_day_on_both_ends(
    action_case: Case, local_tz: Callable[[str], None]
) -> None:
    """수행일 범위는 수행일(요청 시각의 업무 날짜)을 양 끝 포함으로 비교한다."""
    # given: 서버 시간대가 Asia/Seoul이고, 로컬 하루 경계 앞뒤 시각의 Action 4건
    local_tz("Asia/Seoul")
    moments = {  # 로컬(KST) 경계 직전·직후
        "전날 23:59": datetime(2026, 10, 15, 14, 59, tzinfo=UTC),
        "당일 00:00": datetime(2026, 10, 15, 15, 0, tzinfo=UTC),
        "당일 23:59": datetime(2026, 10, 16, 14, 59, tzinfo=UTC),
        "다음날 00:00": datetime(2026, 10, 16, 15, 0, tzinfo=UTC),
    }
    for name, moment in moments.items():
        await action_case.add(make_deal_action(moment, action=name))

    day = date(2026, 10, 16)
    # when: 같은 날을 시작·종료로 걸어 검색한다
    same_day = await action_case.search(acted_from=day, acted_to=day)
    # then: 그 로컬 하루의 Action만 나온다
    assert same_day == ["당일 23:59", "당일 00:00"]
    # when: 시작일만 걸어 검색한다
    from_day = await action_case.search(acted_from=day)
    # then: 그날 00:00부터의 Action이 나온다
    assert from_day == ["다음날 00:00", "당일 23:59", "당일 00:00"]
    # when: 종료일만 걸어 검색한다
    to_day = await action_case.search(acted_to=day)
    # then: 그날 23:59까지의 Action이 나온다
    assert to_day == ["당일 23:59", "당일 00:00", "전날 23:59"]


async def test_search_returns_every_match_without_a_page_limit(action_case: Case) -> None:
    """검색은 쪽 제한 없이 맞는 것을 모두 돌려준다."""
    # given: Action 25건
    for number in range(25):
        await action_case.add(
            make_deal_action(NOW + timedelta(minutes=number), action=f"활동 {number:02d}")
        )

    # when: 조건 없이 검색한다
    found = await action_case.search()
    # then: 25건이 모두 나온다
    assert len(found) == 25


async def test_search_is_scoped_to_the_deal(action_case: Case) -> None:
    """Deal 코드로 검색하면 그 Deal의 Action만 나온다."""
    # given: 기본 Deal의 Action 3건과 다른 Deal의 Action 1건
    await _seed(action_case)
    other = make_deal_action(NOW, action="다른 딜", deal_code=make_deal_code("B002"))
    await action_case.add(other)

    # when: 다른 Deal 코드로 검색한다
    scoped = await action_case.search(deal_code=other.deal_code)
    # then: 그 Deal의 Action만 나온다
    assert scoped == ["다른 딜"]
    # when: Deal 코드 없이 검색한다
    unscoped = await action_case.search()
    # then: 기본 Deal 범위라 다른 Deal의 Action은 섞이지 않는다
    assert "다른 딜" not in unscoped


async def test_filters_by_action_type_id(action_case: Case) -> None:
    """유형 id로 검색하면 그 유형의 Action만 나온다."""
    # given: 통화 1건·미팅 2건의 Action
    await _seed(action_case)

    # when: 통화 유형으로 검색한다
    calls = await action_case.search(action_type_id=await _type_id(action_case, "통화"))
    # then: 통화 Action만 나온다
    assert calls == ["첫 통화"]
    # when: 미팅 유형으로 검색한다
    meetings = await action_case.search(action_type_id=await _type_id(action_case, "미팅"))
    # then: 미팅 Action만 나온다
    assert meetings == [
        "최종 미팅",
        "킥오프 미팅",
    ]
    # when: Action이 없는 유형으로 검색한다
    emails = await action_case.search(action_type_id=await _type_id(action_case, "이메일"))
    # then: 결과가 없다
    assert emails == []


async def test_filters_by_the_id_of_a_custom_type(action_case: Case) -> None:
    """사용자가 만든 유형의 id로도 검색할 수 있다."""
    # given: 새 유형과 그 유형의 Action 1건
    custom = make_action_type("ZZ 검색")
    await action_case.action_types.add(custom)
    await _seed(action_case)
    await action_case.add(make_deal_action(NOW, action="커스텀", action_type=custom.ref))

    # when: 새 유형 id로 검색한다
    found = await action_case.search(action_type_id=custom.id)
    # then: 그 Action만 나온다
    assert found == ["커스텀"]


async def test_an_unknown_type_id_matches_nothing(action_case: Case) -> None:
    """없는 유형 id로 검색하면 아무것도 나오지 않는다."""
    # given: Action 3건
    await _seed(action_case)

    # when: 존재하지 않는 유형 id로 검색한다
    found = await action_case.search(action_type_id=new_id())
    # then: 결과가 없다
    assert found == []


async def test_search_filters_by_type_id_after_the_type_is_renamed(action_case: Case) -> None:
    """유형 이름을 바꿔도 같은 id로 검색되고 새 이름으로 읽힌다."""
    # given: Action 3건과 "통화" 유형을 "전화"로 바꾼 상태
    await _seed(action_case)
    call = next(t for t in await action_case.action_types.list() if t.name == "통화")
    call.rename("전화", NOW)
    await action_case.action_types.update(call)

    # when: 그 유형 id로 검색한다
    found = await action_case.found(action_type_id=call.id)

    # then: 원래 Action이 나오고 유형 이름은 새 이름이다
    assert [a.content.action for a in found] == ["첫 통화"]
    assert found[0].content.action_type.name == "전화"
