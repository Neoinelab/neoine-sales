from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.action_type.entities import ActionType
    from app.domain.action_type.values import ActionTypeId


class ActionTypeRepository(Protocol):
    """Action 유형 저장소 계약. 이름은 대소문자 무시로 고유하다."""

    async def list(self, *, for_update: bool = False) -> Sequence[ActionType]:
        """기본 유형(default_order) 먼저, 직접 만든 것은 소문자 이름(코드 포인트)·id 순.

        for_update=True면 트랜잭션이 끝날 때까지 행을 잠근다.
        """
        ...

    async def get(self, type_id: ActionTypeId) -> ActionType:
        """없으면 ActionTypeNotFoundError."""
        ...

    async def add(self, action_type: ActionType) -> None:
        """이름이 겹치면(대소문자 무시) DuplicateActionTypeNameError, 생성자 users 행이 없으면
        InvalidReferenceError("사용자")."""
        ...

    async def update(self, action_type: ActionType) -> None:
        """이름과 updated_at을 저장한다. 없으면 ActionTypeNotFoundError, 이름이 겹치면
        DuplicateActionTypeNameError."""
        ...

    async def delete(self, type_id: ActionTypeId) -> None:
        """물리 삭제한다. 없으면 ActionTypeNotFoundError, 쓰는 Action이 있으면
        ActionTypeInUseError(실제 건수)."""
        ...
