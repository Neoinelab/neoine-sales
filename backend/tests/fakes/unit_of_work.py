"""InMemory Unit of Work와 고정 시계.

FakeUnitOfWork는 실제 DB 트랜잭션처럼 동작한다: commit한 변경만 남고, commit 없이 블록을 벗어나거나
예외가 나면 블록 안의 변경이 사라진다(commit 이후의 변경도 사라진다).
"""

import copy
from datetime import datetime, timedelta
from typing import Any, Self

from tests.fakes.repositories import (
    FakeCustomerRepository,
    FakeDealRepository,
    FakePartnerRepository,
)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.customers = FakeCustomerRepository()
        self.partners = FakePartnerRepository()
        self.deals = FakeDealRepository()
        self.commits = 0
        self._snapshot: tuple[Any, Any, Any] | None = None

    def _take(self) -> tuple[Any, Any, Any]:
        return (
            copy.deepcopy(self.customers._items),
            copy.deepcopy(self.partners._items),
            copy.deepcopy(self.deals._items),
        )

    async def __aenter__(self) -> Self:
        self._snapshot = self._take()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.rollback()

    async def commit(self) -> None:
        self.commits += 1
        self._snapshot = self._take()

    async def rollback(self) -> None:
        if self._snapshot is not None:
            customers, partners, deals = copy.deepcopy(self._snapshot)
            self.customers._items = customers
            self.partners._items = partners
            self.deals._items = deals


class FixedClock:
    """테스트용 시계. 시간이 자동으로 흐르지 않고 advance로만 움직인다."""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: int = 60) -> None:
        self._now += timedelta(seconds=seconds)
