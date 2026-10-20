"""ListDealActions(AC-14~16): Deal 단위 전부 반환, 필터는 AND, 날짜는 로컬 업무 날짜 양끝 포함."""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.ports.deal_action_repository import DealActionQuery, DealActionSort
from app.domain.action_type.values import ActionTypeId
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from tests.factories_action_type import type_id
from tests.support.user_ids import uid
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
    query = DealActionQuery(deal_code=DealCode("20261016-ZZZZ"))

    with pytest.raises(DealNotFoundError):
        await action_env.list.execute(query)


async def test_list_returns_every_action_of_the_deal_without_paging(action_env: ActionEnv) -> None:
    for number in range(25):
        await action_env.act(KIM, action=f"활동 {number:02d}")

    assert len(await _names(action_env)) == 25


async def test_list_excludes_the_actions_of_other_deals(action_env: ActionEnv) -> None:
    other = await action_env.env.new_deal()
    await action_env.act(KIM, action="내 Deal")
    await action_env.act(KIM, code=other.item.deal.id.value, action="다른 Deal")

    assert await _names(action_env) == ["내 Deal"]


async def test_default_sort_is_latest_acted_at_first_and_ascending_is_available(
    action_env: ActionEnv,
) -> None:
    for name in ("첫째", "둘째", "셋째"):
        await action_env.act(KIM, action=name)

    assert await _names(action_env) == ["셋째", "둘째", "첫째"]
    assert await _names(action_env, sort=DealActionSort.ACTED_AT_DESC) == ["셋째", "둘째", "첫째"]
    assert await _names(action_env, sort=DealActionSort.ACTED_AT_ASC) == ["첫째", "둘째", "셋째"]


async def test_sort_by_due_date_breaks_ties_by_latest_acted_at(action_env: ActionEnv) -> None:
    await action_env.act(KIM, action="늦은 기한", due_date=date(2026, 3, 1))
    await action_env.act(KIM, action="빠른 기한 먼저", due_date=date(2026, 2, 1))
    await action_env.act(KIM, action="빠른 기한 나중", due_date=date(2026, 2, 1))

    names = await _names(action_env, sort=DealActionSort.DUE_DATE_ASC)

    assert names == ["빠른 기한 나중", "빠른 기한 먼저", "늦은 기한"]


async def test_list_filters_combine_with_and(action_env: ActionEnv) -> None:
    await action_env.act(KIM, action="킥오프", action_type="미팅", memo="예산 100%")
    await action_env.act(PARK, action="견적 발송", action_type="이메일", memo="")
    await action_env.act(PARK, action="최종 미팅", action_type="미팅", memo="조건")
    meeting = type_id("미팅")

    assert await _names(action_env, action_type_id=meeting) == ["최종 미팅", "킥오프"]
    assert await _names(action_env, action_type_id=meeting, actor_user_id=uid("park")) == [
        "최종 미팅"
    ]
    assert await _names(action_env, actor_user_id=uid("park"), keyword="견적") == ["견적 발송"]
    assert await _names(action_env, actor_user_id=BOSS.user_id) == []


async def test_filters_by_action_type_id(action_env: ActionEnv) -> None:
    await action_env.act(KIM, action="통화 기록", action_type="통화")
    await action_env.act(KIM, action="데모 기록", action_type="데모")

    assert await _names(action_env, action_type_id=type_id("데모")) == ["데모 기록"]
    assert await _names(action_env, action_type_id=type_id("통화")) == ["통화 기록"]


async def test_unknown_type_id_lists_nothing(action_env: ActionEnv) -> None:
    await action_env.act(KIM, action="통화 기록", action_type="통화")

    assert await _names(action_env, action_type_id=uuid4()) == []


async def test_the_listed_action_carries_the_current_type_name(action_env: ActionEnv) -> None:
    await action_env.act(KIM, action="통화 기록", action_type="통화")
    renamed = await action_env.env.uow.action_types.get(ActionTypeId(type_id("통화")))
    renamed.rename("전화", action_env.env.clock.now())
    await action_env.env.uow.action_types.update(renamed)

    query = DealActionQuery(deal_code=action_env.deal.item.deal.id)
    (listed,) = await action_env.list.execute(query)

    assert listed.content.action_type.name == "전화"


async def test_keyword_matches_the_three_text_fields_ignoring_case_and_wildcards(
    action_env: ActionEnv,
) -> None:
    await action_env.act(KIM, action="Kickoff", next_action="견적서 준비", memo="예산 100%")
    await action_env.act(KIM, action="제안", next_action="CONTRACT 초안", memo="")

    assert await _names(action_env, keyword="kickoff") == ["Kickoff"]
    assert await _names(action_env, keyword="contract") == ["제안"]
    assert await _names(action_env, keyword="100%") == ["Kickoff"]
    assert await _names(action_env, keyword="_") == []


async def test_due_range_is_inclusive_on_both_ends(action_env: ActionEnv) -> None:
    for name, due in (("a", date(2026, 2, 1)), ("b", date(2026, 2, 10)), ("c", date(2026, 3, 1))):
        await action_env.act(KIM, action=name, due_date=due)

    assert await _names(action_env, due_from=date(2026, 2, 1), due_to=date(2026, 2, 10)) == [
        "b",
        "a",
    ]
    assert await _names(action_env, due_from=date(2026, 2, 2)) == ["c", "b"]
    assert await _names(action_env, due_to=date(2026, 1, 31)) == []


async def test_acted_date_range_covers_whole_local_days_on_both_ends(
    action_env: ActionEnv, local_tz: Callable[[str], None]
) -> None:
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

    on_the_day = await _names(
        action_env, acted_from=date(2026, 10, 16), acted_to=date(2026, 10, 16)
    )

    assert sorted(on_the_day) == ["당일 00:00", "당일 23:59"]
    assert sorted(await _names(action_env, acted_from=date(2026, 10, 16))) == [
        "다음날 00:00",
        "당일 00:00",
        "당일 23:59",
    ]
    assert sorted(await _names(action_env, acted_to=date(2026, 10, 15))) == ["전날 23:59"]
