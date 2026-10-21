"""CodeRepository·BantLabelRepository Port의 InMemory 구현(Fake).

도메인 모듈(app.domain.code, app.domain.bant)은 사용 시점에 가져온다. 이 Fake는 FakeUnitOfWork가
항상 만들기 때문에, 모듈 수준에서 import하면 코드·Label과 무관한 테스트의 수집까지 막힌다
(tests/fakes/use_cases.py의 지연 import와 같은 이유).

정렬 계약(SQL 구현과 같다)
- 코드: 종류 선언 순(status → forecast), order, id 문자열 오름차순
- Label: 구분 선언 순(budget → authority → need → timeline), 기본 Label 먼저(default_order),
  직접 만든 Label은 lower(name), id 문자열 오름차순
"""

import copy
from typing import TYPE_CHECKING, Any

from app.domain.common.errors import AlreadyExistsError
from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence
    from enum import StrEnum
    from types import ModuleType

    from app.domain.bant.entities import BantLabel
    from app.domain.bant.values import BantCategory, BantLabelId
    from app.domain.code.entities import Code
    from app.domain.code.values import CodeId, CodeKind


def _code_errors() -> ModuleType:
    from app.domain.code import errors  # noqa: PLC0415 - 지연 import(모듈 설명 참고)

    return errors


def _bant_errors() -> ModuleType:
    from app.domain.bant import errors  # noqa: PLC0415 - 지연 import(모듈 설명 참고)

    return errors


def _code_not_found(code_id: Any) -> Any:  # noqa: ANN401 - NotFoundError 하위 인스턴스
    return _code_errors().CodeNotFoundError(code_id)


def _label_not_found(label_id: Any) -> Any:  # noqa: ANN401 - NotFoundError 하위 인스턴스
    return _bant_errors().BantLabelNotFoundError(label_id)


def _declared_index(member: StrEnum) -> int:
    """StrEnum 멤버의 선언 순번."""
    return list(type(member)).index(member)


class FakeCodeRepository(InMemoryStore["Code"]):
    def __init__(self) -> None:
        super().__init__("code", _code_not_found)
        self._deals: Any = None
        self._actions: Any = None
        # list 호출 기록(종류 인자). 같은 코드 목록을 다시 읽지 않는지 확인하는 용도.
        self.list_calls: list[CodeKind | None] = []

    def wire(self, *, deals: Any, actions: Any = None) -> None:  # noqa: ANN401
        """삭제 시 FK 모사에 쓸 Deal·Action 저장소를 연결한다(FakeUnitOfWork가 호출한다)."""
        self._deals = deals
        self._actions = actions

    async def lock_kind(self, kind: CodeKind) -> None:
        """단일 스레드 Fake에는 경쟁이 없어 잠금 자체는 없다."""

    def _sorted(self, kind: CodeKind | None) -> list[Code]:
        found = [c for c in self._items.values() if kind is None or c.kind is kind]
        found.sort(key=lambda c: (_declared_index(c.kind), c.order, c.id))
        return [copy.deepcopy(c) for c in found]

    def _ensure_unique(self, code: Code) -> None:
        for other in self._items.values():
            if other.id == code.id or other.kind is not code.kind:
                continue
            if other.name.lower() == code.name.lower():
                raise _code_errors().DuplicateCodeNameError(code.name)
            if other.key == code.key:
                raise AlreadyExistsError("code key", code.key.value)

    async def list(
        self, kind: CodeKind | None = None, *, for_update: bool = False
    ) -> Sequence[Code]:
        self.list_calls.append(kind)
        return self._sorted(kind)

    async def get(self, code_id: CodeId) -> Code:
        return self._fetch(code_id)

    async def add(self, code: Code) -> None:
        self._ensure_unique(code)
        self._insert(code)

    async def update(self, code: Code) -> None:
        if code.id in self._items:
            self._ensure_unique(code)
        self._replace(code)

    async def delete(self, code_id: CodeId) -> None:
        """Deal이 쓰면 CodeInUseError(Deal 수), Action만 쓰면 (Action 수). FK RESTRICT 모사."""
        code = self._fetch(code_id)
        field = "status_key" if code.kind.value == "status" else "forecast_key"
        if self._deals is not None:
            count = sum(
                1
                for deal in self._deals._items.values()
                if getattr(deal.sync, field) == code.key.value
            )
            if count:
                raise _code_errors().CodeInUseError(count)
        if self._actions is not None:
            action_count = sum(
                1
                for action in self._actions._items.values()
                if getattr(action.snapshot, field) == code.key.value
            )
            if action_count:
                raise _code_errors().CodeInUseError(action_count, "Action")
        self._remove(code_id)


class FakeBantLabelRepository(InMemoryStore["BantLabel"]):
    def __init__(self) -> None:
        super().__init__("bant_label", _label_not_found)
        self._deals: Any = None

    def wire(self, *, deals: Any) -> None:  # noqa: ANN401
        """삭제 시 FK 모사에 쓸 Deal 저장소를 연결한다(FakeUnitOfWork가 호출한다)."""
        self._deals = deals

    def _sort_key(self, label: BantLabel) -> tuple[int, int, int, str, int]:
        if label.is_default:
            return (_declared_index(label.category), 0, label.default_order or 0, "", label.id)
        return (_declared_index(label.category), 1, 0, label.name.lower(), label.id)

    def _ensure_unique(self, label: BantLabel) -> None:
        for other in self._items.values():
            if other.id == label.id or other.category is not label.category:
                continue
            if other.name.lower() == label.name.lower():
                raise _bant_errors().DuplicateLabelNameError(label.name)

    async def list(
        self, category: BantCategory | None = None, *, for_update: bool = False
    ) -> Sequence[BantLabel]:
        found = [
            label
            for label in self._items.values()
            if category is None or label.category is category
        ]
        found.sort(key=self._sort_key)
        return [copy.deepcopy(label) for label in found]

    async def get(self, label_id: BantLabelId) -> BantLabel:
        return self._fetch(label_id)

    async def add(self, label: BantLabel) -> None:
        self._ensure_unique(label)
        self._insert(label)

    async def update(self, label: BantLabel) -> None:
        if label.id in self._items:
            self._ensure_unique(label)
        self._replace(label)

    async def delete(self, label_id: BantLabelId) -> None:
        """Deal이 선택한 Label이면 LabelInUseError(실제 연결 수). FK RESTRICT 모사."""
        label = self._fetch(label_id)
        if self._deals is not None:
            count = sum(
                1
                for deal in self._deals._items.values()
                if deal.bant.get(label.category) == label_id
            )
            if count:
                raise _bant_errors().LabelInUseError(count)
        self._remove(label_id)
