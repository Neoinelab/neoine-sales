"""InMemory Unit of Work와 고정 시계.

FakeUnitOfWork는 실제 DB 트랜잭션처럼 동작한다: commit한 변경만 남고, commit 없이 블록을 벗어나거나
예외가 나면 블록 안의 변경이 사라진다(commit 이후의 변경도 사라진다).
"""

import copy
from datetime import datetime, timedelta
from typing import Any, Self

from tests.fakes.alert_settings_repository import FakeAlertSettingsRepository
from tests.fakes.attachments import FakeAttachmentRepository
from tests.fakes.catalog import FakeBantLabelRepository, FakeCodeRepository
from tests.fakes.contacts import FakeContactRepository
from tests.fakes.deal_history import FakeDealHistoryRepository
from tests.fakes.directory_settings_repository import FakeDirectorySettingsRepository
from tests.fakes.repositories import (
    FakeDealActionRepository,
    FakeDealRepository,
)
from tests.fakes.session_repository import FakeSessionRepository
from tests.fakes.storage_settings_repository import FakeStorageSettingsRepository
from tests.fakes.user_repository import FakeLoginFailureRepository, FakeUserRepository
from tests.fakes.vendors import FakeVendorRepository


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.contacts = FakeContactRepository()
        self.deals = FakeDealRepository()
        self.deal_actions = FakeDealActionRepository()
        self.deal_history = FakeDealHistoryRepository()
        self.sessions = FakeSessionRepository()
        self.users = FakeUserRepository()
        self.login_failures = FakeLoginFailureRepository()
        self.directory_settings = FakeDirectorySettingsRepository()
        self.storage_settings = FakeStorageSettingsRepository()
        self.alert_settings = FakeAlertSettingsRepository()
        self.attachments = FakeAttachmentRepository()
        self.codes = FakeCodeRepository()
        self.bant_labels = FakeBantLabelRepository()
        self.vendors = FakeVendorRepository()
        self.deals.wire(
            contacts=self.contacts,
            codes=self.codes,
            labels=self.bant_labels,
            vendors=self.vendors,
            actions=self.deal_actions,
            history=self.deal_history,
            attachments=self.attachments,
        )
        self.attachments.wire(deals=self.deals)  # 소속 Deal이 없으면 DealNotFoundError
        # 소속 Deal이 없으면 DealNotFoundError, 스냅숏 코드가 없으면 InvalidReferenceError
        self.deal_actions.wire(deals=self.deals, codes=self.codes)
        # 사용 중인 코드 삭제는 CodeInUseError (FK RESTRICT): Deal 사용이 먼저, Action 스냅숏이 다음
        self.codes.wire(deals=self.deals, actions=self.deal_actions)
        self.bant_labels.wire(deals=self.deals)  # 사용 중인 Label 삭제는 LabelInUseError
        self.vendors.wire(deals=self.deals)  # 사용 중인 Vendor·Solution 삭제는 InUseError
        self.contacts.restrict_delete_by(self.deals)  # FK RESTRICT (고객·파트너 링크 모두)
        self._wire_user_references()
        self.commits = 0
        self._snapshot: tuple[Any, ...] | None = None

    def _wire_user_references(self) -> None:
        """users를 FK로 참조하는 저장소를 연결한다(has_links·물리 삭제 RESTRICT)."""
        deals, actions, history = self.deals, self.deal_actions, self.deal_history
        settings = self.directory_settings
        self.users.add_referrer(
            lambda uid: any(d.details.owner_user_id == uid for d in deals._items.values())
        )
        self.users.add_referrer(
            lambda uid: any(a.actor_user_id == uid for a in actions._items.values())
        )
        self.users.add_referrer(
            lambda uid: any(e.changed_by == uid for e in history._items.values())
        )
        self.users.add_referrer(
            lambda uid: any(s.updated_by == uid for s in settings._items.values())
        )
        storage = self.storage_settings
        self.users.add_referrer(  # storage_settings.updated_by_user_id (AC-16: 저장한 admin)
            lambda uid: any(s.updated_by == uid for s in storage._items.values())
        )
        alerts = self.alert_settings
        self.users.add_referrer(  # alert_settings.updated_by_user_id (P3 AC-11)
            lambda uid: any(s.updated_by == uid for s in alerts._items.values())
        )
        attachments = self.attachments
        self.users.add_referrer(  # deal_attachments.uploaded_by_user_id (AC-16: 첨부를 올린 사용자)
            lambda uid: any(a.uploaded_by == uid for a in attachments._items.values())
        )
        labels = self.bant_labels
        self.users.add_referrer(  # bant_labels.created_by_user_id (AC-15: 만든 사람은 연결 있음)
            lambda uid: any(label.created_by_user_id == uid for label in labels._items.values())
        )

    def _repositories(self) -> tuple[Any, ...]:
        return (
            self.contacts,
            self.deals,
            self.deal_actions,
            self.deal_history,
            self.sessions,
            self.users,
            self.login_failures,
            self.directory_settings,
            self.storage_settings,
            self.alert_settings,
            self.attachments,
            self.codes,
            self.bant_labels,
            self.vendors,
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

    def advance(self, seconds: float = 60) -> None:
        self._now += timedelta(seconds=seconds)


class SteppingClock(FixedClock):
    """now()를 부를 때마다 1초씩 흐르는 시계(생성 순서 정렬 확인용)."""

    def now(self) -> datetime:
        current = self._now
        self._now += timedelta(seconds=1)
        return current
