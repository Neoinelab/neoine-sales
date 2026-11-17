"""Action 수정의 유형 선택: {id}|{name} 해석, 같은 유형이면 변경 없음, 검증 순서.

등록의 유형 규칙은 test_deal_action_type_choice.py. 수정의 판정 순서는 없는 Action 404, 담당자 아님
403, 유형 오류 422, 그 밖의 입력 오류 422다. 실패하면 새 유형도 남지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.choice import CatalogChoice
from app.domain.action_type.errors import UnknownActionTypeError
from app.domain.common.errors import InvalidValueError
from app.domain.deal_action.errors import DealActionEditForbiddenError, DealActionNotFoundError
from app.domain.deal_action.value_objects import DealActionId
from tests.factories_action_type import type_id
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.action_env import ACTION_OR_NEXT_REQUIRED, KIM, PARK

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv

UNKNOWN_TYPE = "선택한 유형이 없습니다. 목록에서 다시 선택하세요."
TYPE_REQUIRED = "유형을 입력하세요."
TYPE_TOO_LONG = "유형은 50자 이내로 입력하세요."


async def _type_names(action_env: ActionEnv) -> list[str]:
    return [t.name for t in await action_env.env.uow.action_types.list()]


# --- 수정 ---


async def test_update_with_new_type_name_creates_type_and_history(action_env: ActionEnv) -> None:
    """새 유형 이름으로 고치면 유형이 생기고 수정 이력이 남는다.

    테스트 코드: AC-053
    """
    # given: 유형 "미팅"인 Action
    action = await action_env.act(KIM, action_type="미팅")

    # when: 유형만 새 이름 "웨비나"로 고친다
    await action_env.update_as(action.id, KIM, action_type=CatalogChoice(name="웨비나"))

    # then: 새 유형이 요청자가 만든 것으로 생긴다
    stored = (await action_env.stored(action.id)).content.action_type
    created = await action_env.env.uow.action_types.get(stored.id)
    assert (created.name, created.created_by_user_id) == ("웨비나", KIM.user_id)
    # then: 이력은 수정 전 "미팅 …"과 수정 후 "수정: 웨비나 …"다
    (_, _, before, after) = (await action_env.rows())[-1]
    assert before.startswith("미팅 · 킥오프 미팅")
    assert after == "수정: 웨비나 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2026-01-15)"


async def test_changing_only_the_type_leaves_exactly_one_history_entry(
    action_env: ActionEnv,
) -> None:
    """유형만 바꿔도 이력 1건이 남는다.

    테스트 코드: AC-053
    """
    # given: 유형 "미팅"인 Action과 이력 건수
    action = await action_env.act(KIM, action_type="미팅")
    entries = len(await action_env.action_entries())

    # when: 유형만 기존 유형 "데모"로 고친다
    await action_env.update_as(action.id, KIM, action_type=CatalogChoice(id=type_id("데모")))

    # then: 이력이 1건 늘고 수정 후 요약은 "수정: 데모 · …"다
    assert len(await action_env.action_entries()) == entries + 1
    assert (await action_env.rows())[-1][3].startswith("수정: 데모 · ")


async def test_same_type_by_id_changes_nothing(action_env: ActionEnv) -> None:
    """같은 유형 id로 고치면 아무것도 바뀌지 않는다.

    테스트 코드: AC-047
    """
    # given: 유형 "미팅"인 Action과 수정 전 이력·커밋 횟수
    action = await action_env.act(KIM, action_type="미팅")
    rows = await action_env.rows()
    commits = action_env.env.uow.commits

    # when: 같은 유형 id로 고친다
    await action_env.update_as(action.id, KIM, action_type=CatalogChoice(id=type_id("미팅")))

    # then: 이력·커밋·수정 시각이 그대로다
    assert await action_env.rows() == rows
    assert action_env.env.uow.commits == commits
    assert (await action_env.stored(action.id)).updated_at == action.updated_at


async def test_same_type_by_name_in_another_case_changes_nothing_and_creates_no_type(
    action_env: ActionEnv,
) -> None:
    """대소문자만 다른 같은 유형 이름이면 변경도 새 유형도 없다.

    테스트 코드: AC-047
    """
    # given: 유형 "Demo"인 Action과 수정 전 이력·유형 목록
    action = await action_env.act(KIM, action_type=CatalogChoice(name="Demo"))
    rows = await action_env.rows()
    names = await _type_names(action_env)

    # when: 유형 이름을 " DEMO "로 고친다
    await action_env.update_as(action.id, KIM, action_type=CatalogChoice(name=" DEMO "))

    # then: 이력·유형 목록이 그대로고 유형 이름은 "Demo"다
    assert await action_env.rows() == rows
    assert await _type_names(action_env) == names
    assert (await action_env.stored(action.id)).content.action_type.name == "Demo"


async def test_update_with_an_unknown_type_id_is_rejected_and_changes_nothing(
    action_env: ActionEnv,
) -> None:
    """없는 유형 id로 고치면 거절되고 Action은 그대로다.

    테스트 코드: AC-053
    """
    # given: 기본 Action과 수정 전 이력
    action = await action_env.act(KIM)
    rows = await action_env.rows()

    # when·then: 없는 유형 id로 고치면 유형 없음 오류다
    with raises_with(UnknownActionTypeError, UNKNOWN_TYPE):
        await action_env.update_as(action.id, KIM, action_type=CatalogChoice(id=new_id()))

    # then: Action 내용과 이력이 그대로다
    assert (await action_env.stored(action.id)).content == action.content
    assert await action_env.rows() == rows


async def test_failed_update_creates_no_type(action_env: ActionEnv) -> None:
    """수정이 다른 이유로 거절되면 새 유형도 남지 않는다.

    테스트 코드: AC-053
    """
    # given: 기본 Action과 유형 목록
    action = await action_env.act(KIM)
    names = await _type_names(action_env)

    # when·then: 새 유형 이름에 빈 내용으로 고치면 내용 오류다
    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        await action_env.update_as(
            action.id,
            KIM,
            action_type=CatalogChoice(name="웨비나"),
            action=" ",
            next_action="",
            due_date=None,
        )

    # then: 유형 목록과 Action 내용이 그대로다
    assert await _type_names(action_env) == names
    assert (await action_env.stored(action.id)).content == action.content


async def test_forbidden_is_reported_before_type_validation(action_env: ActionEnv) -> None:
    """남의 Action에 잘못된 유형을 보내도 권한 오류가 먼저다.

    테스트 코드: AC-057
    """
    # given: KIM이 남긴 Action과 유형 목록
    action = await action_env.act(KIM)
    names = await _type_names(action_env)

    # when·then: 다른 sales가 없는 유형 id로 고치면 권한 오류다
    with pytest.raises(DealActionEditForbiddenError):
        await action_env.update_as(action.id, PARK, action_type=CatalogChoice(id=new_id()))
    # when·then: 다른 sales가 새 유형 이름으로 고쳐도 권한 오류다
    with pytest.raises(DealActionEditForbiddenError):
        await action_env.update_as(action.id, PARK, action_type=CatalogChoice(name="웨비나"))

    # then: 유형 목록이 그대로다
    assert await _type_names(action_env) == names


async def test_missing_action_is_reported_before_type_validation(action_env: ActionEnv) -> None:
    """없는 Action의 수정은 유형 검증보다 먼저 404다.

    테스트 코드: AC-057
    """
    # when·then: 없는 Action을 없는 유형 id로 고치면 Action 없음 오류다
    with pytest.raises(DealActionNotFoundError):
        await action_env.update_as(
            DealActionId(new_id()), KIM, action_type=CatalogChoice(id=new_id())
        )


async def test_blank_type_name_on_update_is_reported_before_progress(
    action_env: ActionEnv,
) -> None:
    """빈 유형 이름은 진행사항 오류보다 먼저 판정된다."""
    # given: 기본 Action
    action = await action_env.act(KIM)

    # when·then: 빈 유형 이름에 빈 내용으로 고치면 유형 오류다
    with raises_with(InvalidValueError, TYPE_REQUIRED):
        await action_env.update_as(
            action.id,
            KIM,
            action_type=CatalogChoice(name=" "),
            action=" ",
            next_action="",
            due_date=None,
        )
