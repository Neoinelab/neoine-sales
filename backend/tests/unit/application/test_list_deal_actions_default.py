"""ListDealActions·GetDealAction: 조건 없는 기본 목록과 한 건 조회(AC 영역)."""

from typing import TYPE_CHECKING

from app.application.ports.deal_action_repository import DealActionQuery
from app.domain.action_type.values import ActionTypeId
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal_action.errors import DealActionNotFoundError
from app.domain.deal_action.value_objects import DealActionId
from tests.factories_action_type import type_id
from tests.support.expect import raises_with
from tests.unit.application.action_env import KIM, NOT_FOUND, PARK

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv

MAX_ID = 2**53 - 1


async def test_listing_returns_only_the_actions_of_that_deal_without_paging(
    action_env: ActionEnv,
) -> None:
    """조건 없이 읽으면 그 Deal의 Action 전부가 페이지 없이 나오고 다른 Deal의 것은 없다.

    테스트 코드: AC-065
    """
    # given: Deal A에 Action 3건, Deal B에 Action 1건
    other = await action_env.env.new_deal()
    for name in ("가", "나", "다"):
        await action_env.act(KIM, action=name)
    await action_env.act(KIM, code=other.item.deal.id.value, action="다른 Deal")

    # when: Deal A의 목록을 조건 없이 읽는다
    found = await action_env.list.execute(DealActionQuery(deal_code=action_env.deal.item.deal.id))

    # then: Deal A의 3건이 모두 있고 Deal B의 것은 없다
    assert sorted(str(a.content.action) for a in found) == ["가", "나", "다"]


async def test_default_order_is_latest_acted_on_first_then_later_registered_first(
    action_env: ActionEnv,
) -> None:
    """기본 목록은 수행일 최신순이고 같은 수행일이면 나중에 등록한 것이 앞이다.

    테스트 코드: AC-066
    """
    # given: 서로 다른 날(하루씩 흐름)의 Action 3건과 마지막 날에 남긴 두 건
    await action_env.act(KIM, action="첫째")
    await action_env.act(KIM, action="둘째", advance=86400)
    await action_env.act(KIM, action="셋째", advance=86400)
    await action_env.act(KIM, action="먼저 등록", advance=86400)
    await action_env.act(KIM, action="나중 등록", advance=0)

    # when: 조건 없이 목록을 읽는다
    found = await action_env.list.execute(DealActionQuery(deal_code=action_env.deal.item.deal.id))

    # then: 수행일 내림차순이고 같은 수행일의 두 건은 나중에 등록한 것이 앞이다
    assert [str(a.content.action) for a in found] == [
        "나중 등록",
        "먼저 등록",
        "셋째",
        "둘째",
        "첫째",
    ]


async def test_listing_a_missing_deal_is_not_found(action_env: ActionEnv) -> None:
    """없는 Deal의 목록은 Deal 없음 오류다.

    테스트 코드: AC-067
    """
    # when·then: 없는 code의 목록을 읽으면 Deal을 찾을 수 없다
    with raises_with(DealNotFoundError, "Deal을 찾을 수 없습니다."):
        await action_env.list.execute(DealActionQuery(deal_code=DealCode("20261016-ZZZZ")))


async def test_list_and_get_show_the_current_type_name_while_history_keeps_the_old_one(
    action_env: ActionEnv,
) -> None:
    """목록과 한 건은 유형의 현재 이름을 보이고 이미 남은 이력 문구는 옛 이름이다.

    테스트 코드: AC-068
    """
    # given: "미팅" Action이 있고 유형 이름이 "회의"로 바뀌었다
    action = await action_env.act(KIM, action_type="미팅")
    meeting = await action_env.env.uow.action_types.get(ActionTypeId(type_id("미팅")))
    meeting.rename("회의", action_env.env.clock.now())
    await action_env.env.uow.action_types.update(meeting)

    # when: 목록과 그 Action 한 건을 읽는다
    (listed,) = await action_env.list.execute(
        DealActionQuery(deal_code=action_env.deal.item.deal.id)
    )
    single = await action_env.get.execute(action.id)

    # then: 두 곳 모두 같은 id의 유형이 현재 이름이다
    assert (listed.content.action_type.id, listed.content.action_type.name) == (
        meeting.id,
        "회의",
    )
    assert single.content.action_type.name == "회의"
    # then: 이미 남은 등록 이력 문구는 옛 이름이다
    assert (await action_env.rows())[-1][3].startswith("등록: 미팅 · ")


async def test_getting_a_missing_action_is_not_found_even_for_the_maximum_id(
    action_env: ActionEnv,
) -> None:
    """없는 Action 한 건 조회는 상한 id여도 Action 없음 오류다.

    테스트 코드: AC-069
    """
    # given: 다른 사용자의 Action만 있는 Deal
    await action_env.act(PARK)

    # when·then: 없는 id와 상한 id를 읽으면 Action을 찾을 수 없다
    with raises_with(DealActionNotFoundError, NOT_FOUND):
        await action_env.get.execute(DealActionId(MAX_ID - 1))
    with raises_with(DealActionNotFoundError, NOT_FOUND):
        await action_env.get.execute(DealActionId(MAX_ID))
