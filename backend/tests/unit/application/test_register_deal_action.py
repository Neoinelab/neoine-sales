"""RegisterDealAction: 수행 일시·담당자는 서버가 채우고, 스냅숏·이력을 남긴다."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.deal.inputs import Actor
from app.application.ports.deal_repository import NextActionSummary
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.sync import SyncState
from app.domain.deal_action.next_action_status import NextActionState, NextActionStatus
from tests.support.expect import raises_with
from tests.support.user_ids import uid
from tests.unit.application.action_env import (
    ACTION_OR_NEXT_REQUIRED,
    DUE_DATE_REQUIRED,
    DUE_WITHOUT_NEXT,
    KIM,
    PARK,
    SUMMARY,
)

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv


async def test_register_action_sets_now_requester_and_current_snapshot(
    action_env: ActionEnv,
) -> None:
    """등록하면 수행 일시·담당자·스냅숏을 서버가 정한다.

    테스트 코드: AC-001
    """
    # given: Status 제품소개·Forecast Best인 Deal
    deal = await action_env.env.new_deal(status_key="introduction", forecast_key="best")
    action_env.env.clock.advance(300)

    # when: KIM이 Action을 등록한다
    action = await action_env.act(KIM, code=deal.item.deal.id.value)

    # then: 수행일(오늘 업무 날짜)·담당자·스냅숏·내용이 서버 값으로 저장된다
    stored = await action_env.stored(action.id)
    assert stored.acted_on == action_env.env.clock.now().astimezone().date()
    assert stored.created_at == stored.updated_at == action_env.env.clock.now()
    assert stored.actor_user_id == KIM.user_id
    assert stored.snapshot == SyncState("introduction", "best")
    assert stored.deal_code == deal.item.deal.id
    assert stored.content.action_type.name == "미팅"
    assert stored.content.next_action == "요구사항 문서 전달"
    assert stored.content.due_date == date(2026, 1, 15)


async def test_register_action_trims_every_text_and_keeps_a_past_due_date(
    action_env: ActionEnv,
) -> None:
    """텍스트 앞뒤 공백을 지워 저장하고 지난 Due Date도 받는다.

    테스트 코드: AC-003
    """
    # when: 공백이 낀 텍스트와 지난 Due Date로 등록한다
    action = await action_env.act(
        action="  킥오프  ", next_action=" 견적 ", due_date=date(2000, 1, 1)
    )

    # then: 공백이 지워진 값과 지난 Due Date가 저장된다
    content = (await action_env.stored(action.id)).content
    assert (content.action, content.next_action) == ("킥오프", "견적")
    assert content.due_date == date(2000, 1, 1)


async def test_register_action_saves_long_text_in_full(action_env: ActionEnv) -> None:
    """진행사항·Next Action은 길이 상한 없이 저장된다.

    테스트 코드: AC-004
    """
    # when: 5,000자·5,000자 텍스트로 등록한다
    action = await action_env.act(action="가" * 5_000, next_action="😀" * 5_000)

    # then: 두 값이 잘리지 않고 저장된다
    content = (await action_env.stored(action.id)).content
    assert content.action is not None
    assert content.next_action is not None
    assert len(content.action) == 5_000
    assert len(content.next_action) == 5_000


@pytest.mark.parametrize("code", ["20261016-ZZZZ", "not-a-code"])
async def test_register_action_on_missing_or_malformed_deal_is_not_found_before_validation(
    action_env: ActionEnv, code: str
) -> None:
    """없는 Deal·형식이 틀린 code는 입력 검증보다 먼저 404다.

    테스트 코드: AC-013
    """
    # when·then: 비어 있는 입력으로 없는 code에 등록하면 Deal 없음 오류다
    with raises_with(DealNotFoundError, "Deal을 찾을 수 없습니다."):
        await action_env.act(code=code, action="  ", next_action="", due_date=None)


async def test_register_action_with_blank_progress_stores_nothing(action_env: ActionEnv) -> None:
    """진행사항·Next Action이 모두 비면 422이고 아무것도 저장되지 않는다.

    테스트 코드: AC-008
    """
    # given: 등록 전 커밋 횟수
    commits = action_env.env.uow.commits

    # when·then: 진행사항·Next Action 없이 등록하면 입력 오류다
    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        await action_env.act(action="   ", next_action="", due_date=None)

    # then: 커밋·이력·Action이 늘지 않는다
    assert action_env.env.uow.commits == commits
    assert await action_env.rows() == []
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_register_action_without_due_date_is_rejected(action_env: ActionEnv) -> None:
    """Next Action이 있는데 Due Date가 없으면 거절한다.

    테스트 코드: AC-009
    """
    # when·then: Due Date 없이 등록하면 Due Date 필수 오류다
    with raises_with(InvalidValueError, DUE_DATE_REQUIRED):
        await action_env.act(due_date=None)

    # then: 저장된 Action이 없다
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_register_action_records_one_action_history_and_keeps_deal_updated_at(
    action_env: ActionEnv,
) -> None:
    """등록하면 이력 1건이 남고 Deal 수정 시각은 그대로다.

    테스트 코드: AC-016, AC-018
    """
    # given: 등록 전 Deal 수정 시각
    before = (await action_env.env.uow.deals.get(action_env.deal.item.deal.id)).updated_at

    # when: KIM이 Action을 등록한다
    action = await action_env.act(KIM)

    # then: "등록: <요약>" 이력 1건이 요청자·요청 시각으로 남는다
    assert await action_env.rows() == [
        ("action", "Action", "", f"등록: {SUMMARY}"),
    ]
    entry = (await action_env.action_entries())[0]
    assert entry.changed_by == KIM.user_id
    assert entry.changed_at == action.created_at
    # then: Deal 수정 시각은 그대로다
    deal = await action_env.env.uow.deals.get(action_env.deal.item.deal.id)
    assert deal.updated_at == before


async def test_register_action_clips_the_history_but_not_the_action(
    action_env: ActionEnv,
) -> None:
    """긴 요약은 이력에서만 1,000자로 잘리고 Action 원문은 그대로다.

    테스트 코드: AC-017
    """
    # when: 진행사항 2,000자로 등록한다
    action = await action_env.act(action="가" * 2_000)

    # then: 이력 변경 후는 1,000자에서 "…"로 끝난다
    (row,) = await action_env.rows()
    assert len(row[3]) == 1_000
    assert row[3].endswith("…")
    # then: Action의 진행사항은 2,000자 그대로다
    progress = (await action_env.stored(action.id)).content.action
    assert progress is not None
    assert len(progress) == 2_000


async def test_the_registered_action_becomes_the_next_action_and_last_update_of_the_deal(
    action_env: ActionEnv,
) -> None:
    """등록한 Action이 Deal의 Next Action·최종 업데이트가 된다.

    테스트 코드: AC-018
    """
    # when: Next Action이 있는 Action을 등록한다
    action = await action_env.act(next_action="계약서 검토", due_date=date(2026, 2, 5))

    # when: Deal 상세를 읽는다
    detail = await action_env.env.get.execute(action_env.code)

    # then: Deal Next Action과 최종 업데이트가 새 Action을 가리킨다
    assert detail.item.next_action == NextActionSummary(
        text="계약서 검토", due_date=date(2026, 2, 5), status=NextActionStatus.OPEN
    )
    assert detail.item.last_updated_on == action.acted_on


async def test_register_action_does_not_need_a_registered_requester_user_row(
    action_env: ActionEnv,
) -> None:
    """요청자의 사용자 행이 없어도 등록할 수 있다."""
    # when: 등록된 사용자가 아닌 요청자가 등록한다
    stranger = Actor(user_id=uid("stranger"), role=Role.SALES)

    action = await action_env.act(stranger)

    # then: 담당자는 그 요청자다
    assert (await action_env.stored(action.id)).actor_user_id == stranger.user_id


async def test_register_progress_only_action(action_env: ActionEnv) -> None:
    """진행사항만 Action은 Next Action·Due·상태가 모두 비어 있다.

    테스트 코드: AC-006
    """
    # when: Next Action 없이 진행사항만 등록한다
    action = await action_env.act(KIM, next_action="")

    # then: Next Action·Due·상태는 없고 이력은 진행사항까지만 쓴다
    stored = await action_env.stored(action.id)
    assert stored.content.action == "킥오프 미팅"
    assert stored.content.next_action is None
    assert stored.content.due_date is None
    assert stored.next_action_state is None
    assert (await action_env.rows())[-1][3] == "등록: 미팅 · 킥오프 미팅"


async def test_register_next_only_action(action_env: ActionEnv) -> None:
    """Next Action만 Action은 진행사항이 없고 상태가 Open이다.

    테스트 코드: AC-007
    """
    # when: 진행사항 없이 Next Action만 등록한다
    action = await action_env.act(KIM, action="")

    # then: 진행사항은 없고 상태는 Open이며 이력에 Next Action이 있다
    stored = await action_env.stored(action.id)
    assert stored.content.action is None
    assert stored.content.next_action == "요구사항 문서 전달"
    assert stored.next_action_state == NextActionState.open()
    assert (await action_env.rows())[-1][3] == (
        "등록: 미팅 / Next Action: 요구사항 문서 전달 (Due 2026-01-15)"
    )


async def test_register_next_action_without_due_date_stores_nothing(
    action_env: ActionEnv,
) -> None:
    """Next Action이 있는데 Due Date가 없으면 아무것도 저장하지 않는다.

    테스트 코드: AC-009
    """
    # when·then: 진행사항 없이 Next Action만 있고 Due Date가 없는 등록은 거절된다
    with raises_with(InvalidValueError, DUE_DATE_REQUIRED):
        await action_env.act(action="", due_date=None)

    # then: 저장된 Action이 없다
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_register_due_date_without_next_action_stores_nothing(
    action_env: ActionEnv,
) -> None:
    """Next Action 없이 Due Date만 있으면 아무것도 저장하지 않는다.

    테스트 코드: AC-010
    """
    # when·then: Next Action 없이 Due Date만 주면 거절된다
    with raises_with(InvalidValueError, DUE_WITHOUT_NEXT):
        await action_env.act(next_action="", due_date=date(2026, 2, 1))

    # then: 저장된 Action이 없다
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_a_progress_only_action_keeps_the_previous_next_action_of_the_deal(
    action_env: ActionEnv,
) -> None:
    """진행사항만 Action을 등록해도 Deal의 Next Action은 이전 것이다."""
    # given: Next Action이 있는 Action이 먼저 있다
    await action_env.act(KIM, next_action="계약서 검토", due_date=date(2026, 2, 5))
    # when: 진행사항만 Action을 이어서 등록한다
    latest = await action_env.act(KIM, next_action="", action="전화 통화")

    # when: Deal 상세를 읽는다
    detail = await action_env.env.get.execute(action_env.code)

    # then: Deal Next Action은 이전 Action의 것이고 최종 업데이트는 새 Action이다
    assert detail.item.next_action == NextActionSummary(
        text="계약서 검토", due_date=date(2026, 2, 5), status=NextActionStatus.OPEN
    )
    assert detail.item.last_updated_on == latest.acted_on


async def test_a_sales_who_is_not_the_deal_owner_can_register_an_action(
    action_env: ActionEnv,
) -> None:
    """Deal Owner가 아닌 sales도 Action을 등록할 수 있다.

    테스트 코드: AC-015
    """
    # given: 다른 사람이 Owner인 Deal
    owner = (await action_env.env.uow.deals.get(action_env.deal.item.deal.id)).details.owner_user_id
    assert owner != PARK.user_id

    # when: Owner가 아닌 PARK이 Action을 등록한다
    action = await action_env.act(PARK)

    # then: 등록되고 담당자는 PARK이다
    assert (await action_env.stored(action.id)).actor_user_id == PARK.user_id
