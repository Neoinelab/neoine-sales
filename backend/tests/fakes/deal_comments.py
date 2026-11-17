"""DealCommentRepository Port의 InMemory 구현(Fake). Deal·Action에 연결된 Comment 저장소.

도메인·Port 모듈(app.domain.deal_comment 등)은 사용 시점에 가져온다. 이 Fake는 FakeUnitOfWork가
항상 만들기 때문에, 모듈 수준 import는 Comment와 무관한 테스트의 수집까지 막는다
(partner_meetings.py와 같은 이유).

계약(SQL 구현과 같다, CM 2.2·CM-R2)
- add: 같은 id는 AlreadyExistsError, 소속 Deal이 없으면 DealNotFoundError, 연결 Action이 없거나
  다른 Deal 소속이면 InvalidReferenceError("Action"), 작성자 행이 없으면
  InvalidReferenceError("사용자")
- get: 없으면 DealCommentNotFoundError
- list_for_deal: 그 Deal 소속 Comment 전부(`action_id`를 주면 그 Action의 것만).
  created_at 내림차순, 같으면 id 내림차순(최근순, CM-R7)
- mark_read(deal_code, comment_ids, at): 그 Deal 소속이면서 read_at이 None인 행만 at으로 채운다.
  다른 Deal의 id·없는 id·이미 읽은 id는 건너뛴다(CM-R28)
- unread_counts(deal_code): read_at이 None인 행을 센다. by_action에는 1 이상인 Action만(CM-R29)
- delete: 물리 삭제. 없으면 DealCommentNotFoundError
- count_for_action: 그 Action에 연결된 Comment 수
- remove_of_deal / remove_of_action: Deal·Action 삭제의 CASCADE
"""

import copy
from typing import TYPE_CHECKING, Any

from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from app.domain.deal.code import DealCode
    from app.domain.deal_action.value_objects import DealActionId
    from app.domain.deal_comment.entities import DealComment
    from app.domain.deal_comment.values import DealCommentId


def _not_found(comment_id: Any) -> Any:  # noqa: ANN401 - NotFoundError 하위 인스턴스
    from app.domain.deal_comment.errors import DealCommentNotFoundError  # noqa: PLC0415

    return DealCommentNotFoundError(comment_id)


class FakeDealCommentRepository(InMemoryStore["DealComment"]):
    def __init__(self) -> None:
        super().__init__("deal_comment", _not_found)
        self._deals: Any = None
        self._actions: Any = None
        self._users: Any = None

    def wire(
        self,
        *,
        deals: Any,  # noqa: ANN401
        actions: Any,  # noqa: ANN401
        users: Any,  # noqa: ANN401
    ) -> None:
        """Deal·Action·작성자 존재 확인(FK 모사)에 쓸 저장소를 연결한다."""
        self._deals = deals
        self._actions = actions
        self._users = users

    def _ensure_references(self, comment: DealComment) -> None:
        from app.domain.common.errors import InvalidReferenceError  # noqa: PLC0415
        from app.domain.deal.errors import DealNotFoundError  # noqa: PLC0415

        if comment.deal_code not in self._deals._items:
            raise DealNotFoundError(comment.deal_code.value)
        if comment.action_id is not None:
            action = self._actions._items.get(comment.action_id)
            if action is None or action.deal_code != comment.deal_code:  # 복합 FK(id, deal_id)
                raise InvalidReferenceError("Action", comment.action_id)
        if comment.author_user_id not in self._users._items:
            raise InvalidReferenceError("사용자", comment.author_user_id)

    # --- 쓰기 ---

    async def add(self, comment: DealComment) -> None:
        if comment.id in self._items:
            self._insert(comment)  # 같은 id는 AlreadyExistsError
        self._ensure_references(comment)
        self._insert(comment)

    async def mark_read(
        self, deal_code: DealCode, comment_ids: Sequence[DealCommentId], at: datetime
    ) -> None:
        wanted = set(comment_ids)
        for comment in self._items.values():
            if comment.id in wanted and comment.deal_code == deal_code and comment.read_at is None:
                comment.read_at = at

    async def delete(self, comment_id: DealCommentId) -> None:
        self._remove(comment_id)

    def remove_of_deal(self, code: DealCode) -> None:
        """Deal 삭제의 CASCADE: 그 Deal 소속 Comment가 모두 지워진다."""
        for comment_id in [i for i, c in self._items.items() if c.deal_code == code]:
            del self._items[comment_id]

    def remove_of_action(self, action_id: DealActionId) -> None:
        """Action 삭제의 CASCADE: 그 Action의 Action Comment만 지워진다."""
        for comment_id in [i for i, c in self._items.items() if c.action_id == action_id]:
            del self._items[comment_id]

    # --- 읽기 ---

    async def get(self, comment_id: DealCommentId, *, for_update: bool = False) -> DealComment:
        return copy.deepcopy(self._fetch(comment_id))

    async def list_for_deal(
        self, deal_code: DealCode, *, action_id: DealActionId | None = None
    ) -> Sequence[DealComment]:
        found = [
            c
            for c in self._items.values()
            if c.deal_code == deal_code and (action_id is None or c.action_id == action_id)
        ]
        found.sort(key=lambda c: (c.created_at, c.id), reverse=True)
        return [copy.deepcopy(c) for c in found]

    async def unread_counts(self, deal_code: DealCode) -> Any:  # noqa: ANN401 - UnreadCommentCounts
        from app.application.deal_comment.views import UnreadCommentCounts  # noqa: PLC0415

        unread = [c for c in self._items.values() if c.deal_code == deal_code and c.read_at is None]
        by_action: dict[Any, int] = {}
        for comment in unread:
            if comment.action_id is not None:
                by_action[comment.action_id] = by_action.get(comment.action_id, 0) + 1
        return UnreadCommentCounts(total=len(unread), by_action=dict(sorted(by_action.items())))

    async def count_for_action(self, action_id: DealActionId) -> int:
        return sum(1 for c in self._items.values() if c.action_id == action_id)

    # --- Fake 안쪽 도우미(다른 Fake가 쓴다) ---

    def bodies_of_action(self, action_id: DealActionId) -> list[str]:
        """그 Action의 Action Comment 본문(키워드 검색용)."""
        return [c.body for c in self._items.values() if c.action_id == action_id]

    def count_for_deal(self, code: DealCode) -> int:
        """그 Deal 소속 Comment 수(삭제 영향용)."""
        return sum(1 for c in self._items.values() if c.deal_code == code)
