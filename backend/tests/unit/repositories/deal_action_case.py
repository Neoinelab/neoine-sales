"""DealActionRepository 계약 테스트 공용 case(Fake와 SQL 구현 양쪽, P2 모델).

Action은 Deal(code) 아래에 있으므로 case가 필요한 Deal·담당자 행을 먼저 만든다. 저장소 준비는
`deal_case.py`와 같다(카탈로그 시드 포함: 스냅숏 key는 codes에 있어야 한다).
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_action_repository import DealActionQuery
from tests.factories import make_deal, make_deal_code
from tests.factories_action_type import attach_catalog_type
from tests.support.user_seed import ensure_users
from tests.unit.repositories.deal_case import DealCase, open_deal_case

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL

    from app.application.ports.deal_action_repository import DealActionRepository
    from app.domain.deal.code import DealCode
    from app.domain.deal_action.entities import DealAction

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


class Case:
    def __init__(self, deal_case: DealCase) -> None:
        self._deal_case = deal_case
        self.repository: DealActionRepository = deal_case.actions
        self.deals = deal_case.deals
        self.codes = deal_case.codes
        self.action_types = deal_case.action_types

    async def ensure_deal(self, code: DealCode) -> None:
        if not await self.deals.exists(code):
            await self._deal_case.add(make_deal(code=code))

    async def ensure_actor(self, action: DealAction) -> None:
        await ensure_users(self._deal_case.users, action.actor_user_id)  # FK: 담당자 행

    async def add(self, action: DealAction) -> None:
        """Deal·담당자 행을 (없으면) 만들고 유형을 저장소의 같은 이름 유형으로 맞춘 뒤 저장한다.

        DB 시드 유형의 id는 무작위라 팩토리의 고정 id는 FK로 통하지 않는다(`attach_catalog_type`).
        """
        await self.ensure_deal(action.deal_code)
        await self.ensure_actor(action)
        await attach_catalog_type(self.action_types, action)
        await self.repository.add(action)

    async def search(self, **criteria: object) -> list[str]:
        """검색 결과의 진행사항 목록(정렬 순서 그대로). deal_code를 생략하면 기본 Deal이다."""
        found = await self.found(**criteria)
        assert all(a.content.action is not None for a in found)
        return [str(a.content.action) for a in found]

    async def found(self, **criteria: object) -> list[DealAction]:
        values = {"deal_code": make_deal_code(), **criteria}
        return list(await self.repository.search(DealActionQuery(**values)))  # type: ignore[arg-type]


@asynccontextmanager
async def open_case(implementation: str, test_database_url: URL | None) -> AsyncIterator[Case]:
    async with open_deal_case(implementation, test_database_url) as deal_case:
        yield Case(deal_case)
