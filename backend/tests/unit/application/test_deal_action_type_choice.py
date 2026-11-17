"""Action 등록·수정의 유형 선택: {id}|{name} 해석, 같은 트랜잭션 생성·롤백, 검증 순서.

유형은 요청의 선택 객체(`CatalogChoice`)로 들어온다. id는 있는 항목을 가리키고, 이름은 대소문자
무시로 찾아 있으면 그 항목을, 없으면 같은 트랜잭션에서 새로 만든다. 저장이 실패하면 새 유형도
남지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.choice import CatalogChoice
from app.application.deal_action.inputs import StatusChangeInput
from app.domain.action_type.errors import UnknownActionTypeError
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import DealNotFoundError
from tests.factories_action_type import make_action_type, type_id
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.action_env import (
    ACTION_OR_NEXT_REQUIRED,
    DUE_DATE_REQUIRED,
    KIM,
    PARK,
)

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv

UNKNOWN_TYPE = "선택한 유형이 없습니다. 목록에서 다시 선택하세요."
TYPE_REQUIRED = "유형을 입력하세요."
TYPE_TOO_LONG = "유형은 50자 이내로 입력하세요."


async def _type_names(action_env: ActionEnv) -> list[str]:
    return [t.name for t in await action_env.env.uow.action_types.list()]


# --- 등록: {id} ---


async def test_type_by_id_is_used(action_env: ActionEnv) -> None:
    """있는 유형 id를 고르면 그 유형이 쓰이고 새 유형은 만들지 않는다.

    테스트 코드: CL-066
    """
    # when: 유형을 {id: 데모}로 골라 Action을 등록한다
    action = await action_env.act(KIM, action_type=CatalogChoice(id=type_id("데모")))

    # then: 저장된 Action의 유형은 '데모'(저장된 id·이름)다
    stored = (await action_env.stored(action.id)).content.action_type
    assert (stored.id, stored.name) == (type_id("데모"), "데모")


async def test_unknown_type_id_is_rejected_and_stores_nothing(action_env: ActionEnv) -> None:
    """없는 유형 id를 고르면 안내 문구로 거절하고 아무것도 저장하지 않는다.

    테스트 코드: CL-067
    """
    # given: 유형 목록 8개
    names = await _type_names(action_env)

    # when: 없는 유형 id로 Action을 등록한다
    with raises_with(UnknownActionTypeError, UNKNOWN_TYPE):
        await action_env.act(KIM, action_type=CatalogChoice(id=new_id()))

    # then: '선택한 유형이 없습니다…' 오류이고 Action·유형·History가 없다
    assert len(action_env.env.uow.deal_actions._items) == 0
    assert await _type_names(action_env) == names
    assert await action_env.rows() == []


# --- 등록: {name} ---


async def test_type_name_reuses_existing_ignoring_case(action_env: ActionEnv) -> None:
    """기존 유형과 대소문자·공백만 다른 이름은 그 유형(저장된 철자)을 쓴다.

    테스트 코드: CL-068
    """
    # given: 'Demo' 유형이 있다
    existing = make_action_type("Demo", created_by=KIM.user_id)
    await action_env.env.uow.action_types.add(existing)
    count = len(await action_env.env.uow.action_types.list())

    # when: ' demo '로 유형을 골라 Action을 등록한다
    action = await action_env.act(KIM, action_type=CatalogChoice(name=" demo "))

    # then: 'Demo' 유형이 쓰이고 유형 수는 그대로다
    stored = (await action_env.stored(action.id)).content.action_type
    assert (stored.id, stored.name) == (existing.id, "Demo")
    assert len(await action_env.env.uow.action_types.list()) == count


async def test_type_name_of_a_seeded_default_reuses_it(action_env: ActionEnv) -> None:
    """기본 유형 이름으로 고르면 그 기본 유형을 쓴다.

    테스트 코드: CL-068
    """
    # when: '  통화 '로 유형을 골라 Action을 등록한다
    action = await action_env.act(KIM, action_type=CatalogChoice(name="  통화 "))

    # then: 기본 '통화' 유형이 쓰이고 유형은 8개 그대로다
    assert (await action_env.stored(action.id)).content.action_type.id == type_id("통화")
    assert len(await _type_names(action_env)) == 8


async def test_unknown_type_name_creates_a_type_by_the_actor(action_env: ActionEnv) -> None:
    """없는 유형 이름이면 요청자가 만든 새 유형이 생긴다.

    테스트 코드: CL-069
    """
    # when: '  웨비나  '로 유형을 골라 Action을 등록한다
    action = await action_env.act(KIM, action_type=CatalogChoice(name="  웨비나  "))

    # then: 요청자가 만든 직접 만든 유형 '웨비나'가 생기고 유형은 9개다
    created = await action_env.env.uow.action_types.get(
        (await action_env.stored(action.id)).content.action_type.id
    )
    assert created.name == "웨비나"
    assert created.is_default is False
    assert created.default_order is None
    assert created.created_by_user_id == KIM.user_id
    assert created.created_at == action_env.env.clock.now()
    assert len(await _type_names(action_env)) == 9


async def test_a_new_type_name_gets_an_allocated_id_and_is_referenced_by_the_action(
    action_env: ActionEnv,
) -> None:
    """새 유형은 새 정수 id를 받고 Action이 그 id를 가리킨다.

    테스트 코드: CL-069
    """
    # when: 없는 이름으로 Action을 등록한다
    action = await action_env.act(KIM, action_type=CatalogChoice(name="웨비나"))

    # then: 새 유형의 id를 Action이 가리킨다
    referenced = (await action_env.stored(action.id)).content.action_type
    created = next(t for t in await action_env.env.uow.action_types.list() if t.name == "웨비나")
    assert created.id == 1  # 이 테이블에서 처음 할당받은 번호(시드는 높은 번호)
    assert referenced.id == created.id


async def test_two_new_type_names_get_increasing_ids(action_env: ActionEnv) -> None:
    """나중에 만든 유형의 id가 더 크다.

    테스트 코드: CL-069
    """
    # when: 새 이름 둘로 Action을 차례로 등록한다
    await action_env.act(KIM, action_type=CatalogChoice(name="웨비나"))
    # then: 두 번째 유형의 id가 더 크다
    await action_env.act(KIM, action_type=CatalogChoice(name="세미나"))

    created = {t.name: t.id for t in await action_env.env.uow.action_types.list()}
    assert (created["웨비나"], created["세미나"]) == (1, 2)


async def test_the_created_type_is_reused_by_the_next_registration(action_env: ActionEnv) -> None:
    """한 번 만든 유형 이름은 다음 선택에서 재사용되고 다시 만들지 않는다.

    테스트 코드: CL-069
    """
    # given: KIM이 '웨비나'로 만든 유형이 있다
    first = await action_env.act(KIM, action_type=CatalogChoice(name="웨비나"))

    # when: PARK이 같은 이름으로 Action을 등록한다
    second = await action_env.act(PARK, action_type=CatalogChoice(name="웨비나"))

    # then: 같은 유형을 쓰고 유형은 9개 그대로다
    first_type = (await action_env.stored(first.id)).content.action_type
    assert (await action_env.stored(second.id)).content.action_type.id == first_type.id
    assert len(await _type_names(action_env)) == 9


async def test_the_new_type_is_saved_together_with_the_action_in_one_commit(
    action_env: ActionEnv,
) -> None:
    """새 유형은 Action과 같은 커밋 한 번으로 저장된다."""
    # given: 등록 전 커밋 횟수
    commits = action_env.env.uow.commits

    # when: 새 유형 이름으로 등록한다
    await action_env.act(KIM, action_type=CatalogChoice(name="웨비나"))

    # then: 커밋은 한 번 늘어난다
    assert action_env.env.uow.commits == commits + 1


# --- 등록 실패는 새 유형을 남기지 않는다 ---


async def test_failed_registration_creates_no_type(action_env: ActionEnv) -> None:
    """새 유형 이름으로 고른 등록이 내용 오류로 거절되면 새 유형이 남지 않는다.

    테스트 코드: AC-019
    """
    # given: 등록 전 유형 목록
    names = await _type_names(action_env)

    # when·then: 새 유형 이름에 내용이 빈 등록을 하면 내용 오류다
    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        await action_env.act(
            KIM,
            action_type=CatalogChoice(name="웨비나"),
            action="   ",
            next_action="",
            due_date=None,
        )

    # then: 유형 목록이 그대로고 Action이 없다
    assert await _type_names(action_env) == names
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_failed_status_change_creates_no_type(action_env: ActionEnv) -> None:
    """새 유형 이름으로 고른 등록이 동반 변경 실패로 거절되면 새 유형이 남지 않는다.

    테스트 코드: AC-019
    """
    # given: 등록 전 유형 목록과 매출 없는 계약완료 변경
    names = await _type_names(action_env)
    change = StatusChangeInput(field="status_key", value="contract_completed")

    # when·then: 새 유형 이름에 매출 없는 계약완료 변경을 실으면 거절된다
    with pytest.raises(InvalidValueError):
        await action_env.act(
            KIM, action_type=CatalogChoice(name="웨비나"), status_changes=(change,)
        )

    # then: 유형 목록이 그대로고 Action이 없다
    assert await _type_names(action_env) == names
    assert len(action_env.env.uow.deal_actions._items) == 0


async def test_a_missing_due_date_creates_no_type(action_env: ActionEnv) -> None:
    """Due Date 없는 등록이 거절되면 새 유형이 남지 않는다.

    테스트 코드: AC-019
    """
    # given: 등록 전 유형 목록
    names = await _type_names(action_env)

    # when·then: 새 유형 이름에 Due Date 없이 등록하면 거절된다
    with raises_with(InvalidValueError, DUE_DATE_REQUIRED):
        await action_env.act(KIM, action_type=CatalogChoice(name="웨비나"), due_date=None)

    # then: 유형 목록이 그대로다
    assert await _type_names(action_env) == names


# --- 검증 순서와 문구 ---


async def test_missing_deal_is_reported_before_type(action_env: ActionEnv) -> None:
    """없는 Deal은 유형 오류보다 먼저 404다.

    테스트 코드: AC-020
    """
    # when·then: 없는 code에 없는 유형 id로 등록하면 Deal 없음 오류다
    with pytest.raises(DealNotFoundError):
        await action_env.act(KIM, code="20261016-ZZZZ", action_type=CatalogChoice(id=new_id()))


async def test_blank_type_name_is_reported_before_progress(action_env: ActionEnv) -> None:
    """빈 유형 이름은 진행사항 오류보다 먼저 판정된다.

    테스트 코드: AC-021
    """
    # when·then: 빈 유형 이름에 빈 진행사항을 주면 유형 오류다
    with raises_with(InvalidValueError, TYPE_REQUIRED):
        await action_env.act(KIM, action_type=CatalogChoice(name="   "), action="  ")


async def test_unknown_type_id_is_reported_before_progress(action_env: ActionEnv) -> None:
    """없는 유형 id는 진행사항 오류보다 먼저 판정된다.

    테스트 코드: AC-021
    """
    # when·then: 없는 유형 id에 빈 진행사항을 주면 유형 없음 오류다
    with raises_with(UnknownActionTypeError, UNKNOWN_TYPE):
        await action_env.act(KIM, action_type=CatalogChoice(id=new_id()), action="  ")


async def test_progress_is_still_reported_before_next_action_and_due_date(
    action_env: ActionEnv,
) -> None:
    """진행사항 오류는 Next Action·Due 오류보다 먼저 판정된다.

    테스트 코드: AC-021
    """
    # when·then: 진행사항·Next Action이 비고 Due도 없으면 진행사항 문구다
    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        await action_env.act(KIM, action="  ", next_action="", due_date=None)


@pytest.mark.parametrize(
    ("name", "message"),
    [("가" * 51, TYPE_TOO_LONG), ("", TYPE_REQUIRED), ("   ", TYPE_REQUIRED)],
    ids=["51-chars", "empty", "blank"],
)
async def test_type_name_rules_apply_to_a_requested_name(
    action_env: ActionEnv, name: str, message: str
) -> None:
    """이름으로 고른 유형도 공백뿐·빈 이름·51자는 유형 문구로 거절한다.

    테스트 코드: CL-070
    """
    # when: 유효하지 않은 이름으로 유형을 골라 등록한다
    with raises_with(InvalidValueError, message):
        await action_env.act(KIM, action_type=CatalogChoice(name=name))

    # then: 필수·길이 문구 오류이고 유형은 8개 그대로다
    assert len(await _type_names(action_env)) == 8


async def test_a_50_code_point_type_name_is_accepted(action_env: ActionEnv) -> None:
    """이름으로 고른 유형은 이모지 50개(50 코드 포인트)까지 허용된다.

    테스트 코드: CL-070
    """
    # when: 이모지 50개 이름으로 Action을 등록한다
    action = await action_env.act(KIM, action_type=CatalogChoice(name="😀" * 50))

    # then: 유형이 그 이름으로 저장된다
    assert (await action_env.stored(action.id)).content.action_type.name == "😀" * 50


async def test_nul_in_a_requested_type_name_is_rejected(action_env: ActionEnv) -> None:
    """NUL 문자가 든 유형 이름은 거절하고 유형을 만들지 않는다.

    테스트 코드: CL-070
    """
    # when: NUL이 든 이름으로 Action을 등록한다
    with pytest.raises(InvalidValueError, match="NUL"):
        await action_env.act(KIM, action_type=CatalogChoice(name="웨\x00비나"))

    # then: NUL 오류이고 유형은 8개 그대로다
    assert len(await _type_names(action_env)) == 8


# --- 이력 문구 ---


async def test_history_uses_the_chosen_type_name(action_env: ActionEnv) -> None:
    """이력 요약의 유형 자리에는 고른(새로 만든) 유형 이름이 들어간다.

    테스트 코드: AC-022
    """
    # when: 새 유형 이름 "웨비나"로 등록한다
    await action_env.act(KIM, action_type=CatalogChoice(name="웨비나"))

    # then: 등록 이력의 유형 자리는 "웨비나"다
    (row,) = await action_env.rows()
    assert row[3] == (
        "등록: 웨비나 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2026-01-15)"
    )


async def test_a_too_long_type_name_is_reported_before_progress(action_env: ActionEnv) -> None:
    """51자 유형 이름은 진행사항 오류보다 먼저 판정된다.

    테스트 코드: AC-021
    """
    # when·then: 51자 유형 이름에 빈 진행사항을 주면 길이 문구다
    with raises_with(InvalidValueError, TYPE_TOO_LONG):
        await action_env.act(KIM, action_type=CatalogChoice(name="가" * 51), action="  ")
