"""ActionTypeRepository Port의 InMemory 구현(Fake).

도메인 모듈(app.domain.action_type)은 사용 시점에 가져온다. 이 Fake는 FakeUnitOfWork가 항상 만들기
때문에 모듈 수준에서 import하면 Action 유형과 무관한 테스트의 수집까지 막힌다
(tests/fakes/catalog.py와 같은 이유).

정렬 계약(SQL 구현과 같다): 기본 유형 먼저(default_order), 직접 만든 유형은 lower(name) 코드 포인트
순, 같으면 id 문자열 순. 이름 중복은 대소문자 무시, 생성자 users 행이 없으면 InvalidReferenceError,
쓰는 Action이 있으면 삭제할 수 없다(FK RESTRICT).
"""

import copy
from typing import TYPE_CHECKING, Any

from app.domain.common.errors import InvalidReferenceError
from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import ModuleType

    from app.domain.action_type.entities import ActionType
    from app.domain.action_type.values import ActionTypeId


def _errors() -> ModuleType:
    from app.domain.action_type import errors  # noqa: PLC0415 - 지연 import(모듈 설명 참고)

    return errors


def _not_found(type_id: Any) -> Any:  # noqa: ANN401 - NotFoundError 하위 인스턴스
    return _errors().ActionTypeNotFoundError(type_id)


class FakeActionTypeRepository(InMemoryStore["ActionType"]):
    def __init__(self) -> None:
        super().__init__("action_type", _not_found)
        self._actions: Any = None
        self._users: Any = None

    def wire(self, *, actions: Any, users: Any = None) -> None:  # noqa: ANN401
        """삭제 시 FK 모사에 쓸 Action 저장소와 생성자 확인에 쓸 사용자 저장소를 연결한다."""
        self._actions = actions
        self._users = users

    @staticmethod
    def _sort_key(item: ActionType) -> tuple[int, int, str, str]:
        if item.is_default:
            return (0, item.default_order or 0, "", str(item.id))
        return (1, 0, item.name.lower(), str(item.id))

    def _ensure_unique(self, item: ActionType) -> None:
        for other in self._items.values():
            if other.id != item.id and other.name.lower() == item.name.lower():
                raise _errors().DuplicateActionTypeNameError(item.name)

    def _ensure_creator(self, item: ActionType) -> None:
        creator = item.created_by_user_id
        if creator is not None and self._users is not None and creator not in self._users._items:
            raise InvalidReferenceError("사용자", creator)

    async def list(self, *, for_update: bool = False) -> Sequence[ActionType]:
        return [copy.deepcopy(item) for item in sorted(self._items.values(), key=self._sort_key)]

    async def get(self, type_id: ActionTypeId) -> ActionType:
        return self._fetch(type_id)

    async def add(self, action_type: ActionType) -> None:
        self._ensure_unique(action_type)
        self._ensure_creator(action_type)
        self._insert(action_type)

    async def update(self, action_type: ActionType) -> None:
        if action_type.id in self._items:
            self._ensure_unique(action_type)
        self._replace(action_type)

    async def delete(self, type_id: ActionTypeId) -> None:
        """쓰는 Action이 있으면 ActionTypeInUseError(실제 건수). FK RESTRICT 모사."""
        self._fetch(type_id)
        if self._actions is not None:
            usage = sum(
                1
                for action in self._actions._items.values()
                if action.content.action_type.id == type_id
            )
            if usage:
                raise _errors().ActionTypeInUseError(usage)
        self._remove(type_id)
