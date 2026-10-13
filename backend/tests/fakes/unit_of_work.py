"""InMemory Unit of Work와 고정 시계.

FakeUnitOfWork는 실제 DB 트랜잭션처럼 동작한다: commit한 변경만 남고, commit 없이 블록을 벗어나거나
예외가 나면 블록 안의 변경이 사라진다(commit 이후의 변경도 사라진다).
"""

import copy
from datetime import datetime, timedelta
from typing import Any, Self

from tests.fakes.directory_settings_repository import FakeDirectorySettingsRepository
from tests.fakes.repositories import (
    FakeCustomerRepository,
    FakeDealActionRepository,
    FakeDealRepository,
    FakePartnerRepository,
    FakeSessionRepository,
)
from tests.fakes.stage_change_repository import FakeDealStageChangeRepository
from tests.fakes.user_repository import FakeLoginFailureRepository, FakeUserRepository


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.customers = FakeCustomerRepository()
        self.partners = FakePartnerRepository()
        self.deals = FakeDealRepository()
        self.deal_actions = FakeDealActionRepository()
        self.deal_stage_changes = FakeDealStageChangeRepository()
        self.deals.restrict_delete_by(self.deal_actions, self.deal_stage_changes)  # FK RESTRICT
        self.customers.restrict_delete_by(self.deals)  # FK RESTRICT
        self.partners.restrict_delete_by(self.deals)  # FK RESTRICT
        self.sessions = FakeSessionRepository()
        self.users = FakeUserRepository()
        self.login_failures = FakeLoginFailureRepository()
        self.directory_settings = FakeDirectorySettingsRepository()
        self.commits = 0
        self._snapshot: tuple[Any, ...] | None = None

    def _repositories(self) -> tuple[Any, ...]:
        return (
            self.customers,
            self.partners,
            self.deals,
            self.deal_actions,
            self.deal_stage_changes,
            self.sessions,
            self.users,
            self.login_failures,
            self.directory_settings,
        )

    def _take(self) -> tuple[Any, ...]:
        return tuple(copy.deepcopy(repo._items) for repo in self._repositories())

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
            for repo, items in zip(
                self._repositories(), copy.deepcopy(self._snapshot), strict=True
            ):
                repo._items = items


class FixedClock:
    """테스트용 시계. 시간이 자동으로 흐르지 않고 advance로만 움직인다."""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: int = 60) -> None:
        self._now += timedelta(seconds=seconds)


class SteppingClock(FixedClock):
    """now()를 부를 때마다 1초씩 흐르는 시계(생성 순서 정렬 확인용)."""

    def now(self) -> datetime:
        current = self._now
        self._now += timedelta(seconds=1)
        return current
