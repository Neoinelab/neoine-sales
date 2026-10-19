"""Action 등록·수정의 유형 선택(AC-7~13·15): {id}|{name} 해석, 같은 트랜잭션 생성·롤백, 검증 순서.

유형은 요청의 선택 객체(`CatalogChoice`)로 들어온다. id는 있는 항목을 가리키고, 이름은 대소문자
무시로 찾아 있으면 그 항목을, 없으면 같은 트랜잭션에서 새로 만든다. 저장이 실패하면 새 유형도
남지 않는다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from app.application.choice import CatalogChoice
from app.domain.action_type.errors import UnknownActionTypeError

from app.application.deal_action.inputs import StatusChangeInput
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import DealNotFoundError
from tests.factories_action_type import make_action_type, type_id
from tests.support.expect import raises_with
from tests.unit.application.action_env import KIM, PARK, PROGRESS_REQUIRED

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv

UNKNOWN_TYPE = "선택한 유형이 없습니다. 목록에서 다시 선택하세요."
TYPE_REQUIRED = "유형을 입력하세요."
TYPE_TOO_LONG = "유형은 50자 이내로 입력하세요."


async def _type_names(action_env: ActionEnv) -> list[str]:
    return [t.name for t in await action_env.env.uow.action_types.list()]


# --- 등록: {id} (AC-7·8) ---


async def test_type_by_id_is_used(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM, action_type=CatalogChoice(id=type_id("데모")))

    stored = (await action_env.stored(action.id)).content.action_type
    assert (stored.id, stored.name) == (type_id("데모"), "데모")


async def test_unknown_type_id_is_rejected_and_stores_nothing(action_env: ActionEnv) -> None:
    names = await _type_names(action_env)

    with raises_with(UnknownActionTypeError, UNKNOWN_TYPE):
        await action_env.act(KIM, action_type=CatalogChoice(id=uuid4()))

    assert len(action_env.env.uow.deal_actions._items) == 0
    assert await _type_names(action_env) == names
    assert await action_env.rows() == []


# --- 등록: {name} (AC-9·10) ---


async def test_type_name_reuses_existing_ignoring_case(action_env: ActionEnv) -> None:
    existing = make_action_type("Demo", created_by=KIM.user_id)
    await action_env.env.uow.action_types.add(existing)
    count = len(await action_env.env.uow.action_types.list())

    action = await action_env.act(KIM, action_type=CatalogChoice(name=" demo "))

    stored = (await action_env.stored(action.id)).content.action_type
    assert (stored.id, stored.name) == (existing.id, "Demo")
    assert len(await action_env.env.uow.action_types.list()) == count


async def test_type_name_of_a_seeded_default_reuses_it(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM, action_type=CatalogChoice(name="  통화 "))

    assert (await action_env.stored(action.id)).content.action_type.id == type_id("통화")
    assert len(await _type_names(action_env)) == 8


async def test_unknown_type_name_creates_a_type_by_the_actor(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM, action_type=CatalogChoice(name="  웨비나  "))

    created = await action_env.env.uow.action_types.get(
        (await action_env.stored(action.id)).content.action_type.id
    )
    assert created.name == "웨비나"
    assert created.is_default is False
    assert created.default_order is None
    assert created.created_by_user_id == KIM.user_id
    assert created.created_at == action_env.env.clock.now()
    assert len(await _type_names(action_env)) == 9


async def test_the_created_type_is_reused_by_the_next_registration(action_env: ActionEnv) -> None:
    first = await action_env.act(KIM, action_type=CatalogChoice(name="웨비나"))

    second = await action_env.act(PARK, action_type=CatalogChoice(name="웨비나"))

    first_type = (await action_env.stored(first.id)).content.action_type
    assert (await action_env.stored(second.id)).content.action_type.id == first_type.id
    assert len(await _type_names(action_env)) == 9


async def test_the_new_type_is_saved_together_with_the_action_in_one_commit(
    action_env: ActionEnv,
) -> None:
    commits = action_env.env.uow.commits

    await action_env.act(KIM, action_type=CatalogChoice(name="웨비나"))

    assert action_env.env.uow.commits == commits + 1


# --- 등록 실패는 새 유형을 남기지 않는다 (AC-11) ---


async def test_failed_registration_creates_no_type(action_env: ActionEnv) -> None:
    names = await _type_names(action_env)

    with raises_with(InvalidValueError, PROGRESS_REQUIRED):
        await action_env.act(KIM, action_type=CatalogChoice(name="웨비나"), action="   ")

    assert await _type_names(action_env) == names
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_failed_status_change_creates_no_type(action_env: ActionEnv) -> None:
    names = await _type_names(action_env)
    change = StatusChangeInput(field="status_key", value="contract_completed")

    with pytest.raises(InvalidValueError):
        await action_env.act(KIM, action_type=CatalogChoice(name="웨비나"), status_change=change)

    assert await _type_names(action_env) == names
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_a_missing_due_date_creates_no_type(action_env: ActionEnv) -> None:
    names = await _type_names(action_env)

    with raises_with(InvalidValueError, "Due Date를 입력하세요."):
        await action_env.act(KIM, action_type=CatalogChoice(name="웨비나"), due_date=None)

    assert await _type_names(action_env) == names


# --- 검증 순서와 문구 (AC-3·12) ---


async def test_missing_deal_is_reported_before_type(action_env: ActionEnv) -> None:
    with pytest.raises(DealNotFoundError):
        await action_env.act(KIM, code="20261016-ZZZZ", action_type=CatalogChoice(id=uuid4()))


async def test_blank_type_name_is_reported_before_progress(action_env: ActionEnv) -> None:
    with raises_with(InvalidValueError, TYPE_REQUIRED):
        await action_env.act(KIM, action_type=CatalogChoice(name="   "), action="  ")


async def test_unknown_type_id_is_reported_before_progress(action_env: ActionEnv) -> None:
    with raises_with(UnknownActionTypeError, UNKNOWN_TYPE):
        await action_env.act(KIM, action_type=CatalogChoice(id=uuid4()), action="  ")


async def test_progress_is_still_reported_before_next_action_and_due_date(
    action_env: ActionEnv,
) -> None:
    with raises_with(InvalidValueError, PROGRESS_REQUIRED):
        await action_env.act(KIM, action="  ", next_action="", due_date=None)


@pytest.mark.parametrize(
    ("name", "message"),
    [("가" * 51, TYPE_TOO_LONG), ("", TYPE_REQUIRED)],
    ids=["51-chars", "empty"],
)
async def test_type_name_rules_apply_to_a_requested_name(
    action_env: ActionEnv, name: str, message: str
) -> None:
    with raises_with(InvalidValueError, message):
        await action_env.act(KIM, action_type=CatalogChoice(name=name))

    assert len(await _type_names(action_env)) == 8


async def test_a_50_code_point_type_name_is_accepted(action_env: ActionEnv) -> None:
    action = await action_env.act(KIM, action_type=CatalogChoice(name="😀" * 50))

    assert (await action_env.stored(action.id)).content.action_type.name == "😀" * 50


async def test_nul_in_a_requested_type_name_is_rejected(action_env: ActionEnv) -> None:
    with pytest.raises(InvalidValueError, match="NUL"):
        await action_env.act(KIM, action_type=CatalogChoice(name="웨\x00비나"))

    assert len(await _type_names(action_env)) == 8


# --- 이력 문구 (AC-15) ---


async def test_history_uses_the_chosen_type_name(action_env: ActionEnv) -> None:
    await action_env.act(KIM, action_type=CatalogChoice(name="웨비나"), memo="")

    (row,) = await action_env.rows()
    assert row[3] == (
        "등록: 웨비나 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2026-01-15)"
    )
