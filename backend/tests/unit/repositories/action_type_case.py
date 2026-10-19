"""ActionTypeRepository 계약 테스트 공용 case(Fake와 SQL 구현 양쪽).

SQL 구현은 마이그레이션이 넣은 기본 유형 8개가 같은 DB에 있고 Fake도 같은 시드를 갖는다. 그래서
계약 테스트는 비어 있는 저장소를 가정하지 않는다(자기가 만든 행만 골라 비교한다: `mine`). 이름은
시드와 겹치지 않는 값을 쓴다. 사용 중 삭제 계약을 위해 Deal과 Action을 만드는 도우미를 가진다.
Deal 저장소 case(`deal_case.py`) 위에 올려, Fake는 FK 모사가 연결된 FakeUnitOfWork를 쓴다.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from tests.factories import make_deal, make_deal_action, make_deal_code
from tests.support.user_seed import ensure_users
from tests.unit.repositories.deal_case import PARAMS, DealCase, open_deal_case

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Collection

    from app.domain.action_type.entities import ActionType
    from sqlalchemy.engine import URL

    from app.domain.deal_action.entities import DealAction
    from app.domain.user.value_objects import UserId

__all__ = ["PARAMS", "ActionTypeCase", "open_action_type_case"]


class ActionTypeCase:
    """한 구현(fake 또는 sql)의 유형 저장소와, 유형을 쓰는 Action을 만드는 도우미."""

    def __init__(self, deal_case: DealCase) -> None:
        self._deal_case = deal_case
        self.types: Any = deal_case.action_types
        self.actions: Any = deal_case.actions

    async def ensure_user(self, user_id: UserId) -> None:
        """유형 생성자 행(FK)을 만든다."""
        await ensure_users(self._deal_case.users, user_id)

    async def mine(self, ids: Collection[Any]) -> list[Any]:
        """저장소 목록 중 ids에 있는 유형만(저장소 순서 유지)."""
        return [t for t in await self.types.list() if t.id in ids]

    async def use(self, action_type: ActionType, *, count: int = 1) -> list[DealAction]:
        """action_type을 쓰는 Action을 count건 저장한다(같은 Deal 하나에)."""
        code = make_deal_code("T001")
        if not await self._deal_case.deals.exists(code):
            await self._deal_case.add(make_deal(code=code))
        made = []
        for _ in range(count):
            action = make_deal_action(deal_code=code, action_type=action_type.ref)
            await ensure_users(self._deal_case.users, action.actor_user_id)
            await self.actions.add(action)
            made.append(action)
        return made


@asynccontextmanager
async def open_action_type_case(
    implementation: str, test_database_url: URL | None
) -> AsyncIterator[ActionTypeCase]:
    async with open_deal_case(implementation, test_database_url) as deal_case:
        yield ActionTypeCase(deal_case)
