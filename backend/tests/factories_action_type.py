"""Action 유형 테스트용 생성 도우미와 기본 유형 표. 기본은 유효한 더미 값이다.

기본 유형 8개의 이름·순서는 마이그레이션 시드와 같다(`tests/fakes/catalog_seed.py`).
Fake 시드의 id는 이름에서 정해지는 고정 값(`type_id`)이라
`make_type_ref("미팅")`이 Fake에 시드된 유형을 가리킨다.
실제 DB의 시드 id는 무작위이므로 SQL 계약 테스트는 `attach_catalog_type`으로 저장소의 같은 이름
유형에 맞춘다. 도메인 모듈은 사용 시점에 가져온다(구현 전에도 이 모듈을 쓰는 다른 테스트의 수집이
막히지 않게).
"""

from typing import TYPE_CHECKING, Any, Final
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from tests.factories import NOW

if TYPE_CHECKING:
    from app.domain.action_type.entities import ActionType
    from app.domain.action_type.values import ActionTypeRef

    from app.domain.deal_action.entities import DealAction

DEFAULT_ACTION_TYPE_NAMES: Final = (
    "통화",
    "미팅",
    "이메일",
    "데모",
    "제안",
    "협상",
    "계약",
    "기타",
)


def type_id(name: str) -> UUID:
    """이름에서 정해지는 고정 id(Fake 시드와 팩토리가 같은 id를 쓴다)."""
    return uuid5(NAMESPACE_URL, f"neoine-sales/action-type/{name}")


def make_type_ref(name: str = "미팅", *, entity_id: UUID | None = None) -> ActionTypeRef:
    """Action이 가리키는 유형 참조. 기본은 Fake 시드의 같은 이름 유형과 같은 id다."""
    from app.domain.action_type.values import ActionTypeId, ActionTypeRef  # noqa: PLC0415

    return ActionTypeRef(id=ActionTypeId(entity_id or type_id(name)), name=name)


def make_action_type(name: str = "ZZ 유형", **overrides: Any) -> ActionType:  # noqa: ANN401
    """저장하지 않은 유형. overrides: is_default, default_order, created_by, now, type_uuid.

    기본 유형이면 is_default=True와 default_order를 함께 준다(DB CHECK).
    """
    from app.domain.action_type.entities import ActionType  # noqa: PLC0415
    from app.domain.action_type.values import ActionTypeId  # noqa: PLC0415

    now = overrides.pop("now", NOW)
    values: dict[str, Any] = {
        "is_default": False,
        "default_order": None,
        "created_by": None,
        "type_uuid": uuid4(),
        **overrides,
    }
    return ActionType(
        id=ActionTypeId(values["type_uuid"]),
        name=name,
        is_default=values["is_default"],
        default_order=values["default_order"],
        created_by_user_id=values["created_by"],
        created_at=now,
        updated_at=now,
    )


def default_action_types(now: Any = NOW) -> list[ActionType]:  # noqa: ANN401
    """마이그레이션 시드와 같은 기본 유형 8개(default_order 1~8, 생성자 없음)."""
    return [
        make_action_type(
            name,
            is_default=True,
            default_order=order,
            type_uuid=type_id(name),
            now=now,
        )
        for order, name in enumerate(DEFAULT_ACTION_TYPE_NAMES, start=1)
    ]


async def attach_catalog_type(types: Any, action: DealAction) -> None:  # noqa: ANN401
    """action이 가리키는 유형을 저장소(types: ActionTypeRepository)의 같은 이름 유형으로 맞춘다.

    실제 DB 시드의 id는 무작위라 팩토리의 고정 id가 FK로 통하지 않는다. 같은 이름의 유형이 있으면
    그 id로 바꾸고, 없으면 그 이름의 유형을 만든다. action.content를 직접 바꿔 테스트가 저장 전 값과
    읽은 값을 그대로 비교할 수 있게 한다.
    """
    from dataclasses import replace  # noqa: PLC0415

    ref = action.content.action_type
    found = next((t for t in await types.list() if t.name.lower() == ref.name.lower()), None)
    if found is None:
        found = make_action_type(ref.name, type_uuid=ref.id)
        await types.add(found)
    action.content = replace(action.content, action_type=found.ref)
