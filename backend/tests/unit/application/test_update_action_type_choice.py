"""Action 수정의 유형 선택(AC-11~13): {id}|{name} 해석, 같은 유형이면 변경 없음, 검증 순서.

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


# --- 수정 (AC-11~13) ---


async def test_update_with_new_type_name_creates_type_and_history(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM, action_type="미팅", memo="")

    await action_env.update_as(action.id, KIM, action_type=CatalogChoice(name="웨비나"), memo="")

    stored = (await action_env.stored(action.id)).content.action_type
    created = await action_env.env.uow.action_types.get(stored.id)
    assert (created.name, created.created_by_user_id) == ("웨비나", KIM.user_id)
    (_, _, before, after) = (await action_env.rows())[-1]
    assert before.startswith("미팅 · 킥오프 미팅")
    assert after == "수정: 웨비나 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2026-01-15)"


async def test_changing_only_the_type_leaves_exactly_one_history_entry(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM, action_type="미팅")
    entries = len(await action_env.action_entries())

    await action_env.update_as(action.id, KIM, action_type=CatalogChoice(id=type_id("데모")))

    assert len(await action_env.action_entries()) == entries + 1
    assert (await action_env.rows())[-1][3].startswith("수정: 데모 · ")


async def test_same_type_by_id_changes_nothing(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM, action_type="미팅")
    rows = await action_env.rows()
    commits = action_env.env.uow.commits

    await action_env.update_as(action.id, KIM, action_type=CatalogChoice(id=type_id("미팅")))

    assert await action_env.rows() == rows
    assert action_env.env.uow.commits == commits
    assert (await action_env.stored(action.id)).updated_at == action.updated_at


async def test_same_type_by_name_in_another_case_changes_nothing_and_creates_no_type(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM, action_type=CatalogChoice(name="Demo"))
    rows = await action_env.rows()
    names = await _type_names(action_env)

    await action_env.update_as(action.id, KIM, action_type=CatalogChoice(name=" DEMO "))

    assert await action_env.rows() == rows
    assert await _type_names(action_env) == names
    assert (await action_env.stored(action.id)).content.action_type.name == "Demo"


async def test_update_with_an_unknown_type_id_is_rejected_and_changes_nothing(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)
    rows = await action_env.rows()

    with raises_with(UnknownActionTypeError, UNKNOWN_TYPE):
        await action_env.update_as(action.id, KIM, action_type=CatalogChoice(id=new_id()))

    assert (await action_env.stored(action.id)).content == action.content
    assert await action_env.rows() == rows


async def test_failed_update_creates_no_type(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)
    names = await _type_names(action_env)

    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        await action_env.update_as(
            action.id,
            KIM,
            action_type=CatalogChoice(name="웨비나"),
            action=" ",
            next_action="",
            due_date=None,
        )

    assert await _type_names(action_env) == names
    assert (await action_env.stored(action.id)).content == action.content


async def test_forbidden_is_reported_before_type_validation(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM)
    names = await _type_names(action_env)

    with pytest.raises(DealActionEditForbiddenError):
        await action_env.update_as(action.id, PARK, action_type=CatalogChoice(id=new_id()))
    with pytest.raises(DealActionEditForbiddenError):
        await action_env.update_as(action.id, PARK, action_type=CatalogChoice(name="웨비나"))

    assert await _type_names(action_env) == names


async def test_missing_action_is_reported_before_type_validation(action_env: ActionEnv) -> None:
    with pytest.raises(DealActionNotFoundError):
        await action_env.update_as(
            DealActionId(new_id()), KIM, action_type=CatalogChoice(id=new_id())
        )


async def test_blank_type_name_on_update_is_reported_before_progress(
    action_env: ActionEnv,
) -> None:
    action = await action_env.act(KIM)

    with raises_with(InvalidValueError, TYPE_REQUIRED):
        await action_env.update_as(
            action.id,
            KIM,
            action_type=CatalogChoice(name=" "),
            action=" ",
            next_action="",
            due_date=None,
        )
