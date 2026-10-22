"""Deal 저장소 계약 테스트 공용 case(Fake와 SQL 구현 양쪽, P1 모델).

한 case는 Deal·이력·활동 저장소와, 이들이 참조하는 연락처·사용자·코드·BANT Label 저장소를 함께
가진다. Fake는 `FakeUnitOfWork`가 연결한(FK 모사) 저장소와 기본 코드·Label 시드를 쓰고, SQL은
한 세션 위의 Sql 저장소들을 쓴다(마이그레이션이 기본 코드·Label을 이미 넣어 두었다). SQL 구현 모듈은
사용 시점에 가져온다.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from app.application.ports.deal_action_repository import DealActionQuery
from app.domain.contact.errors import ContactNotFoundError
from app.domain.contact.values import ContactKind
from tests.factories import NOW, make_deal_action
from tests.factories_action_type import attach_catalog_type
from tests.factories_catalog import make_label
from tests.factories_contact import make_contact
from tests.factories_vendor import store_vendor
from tests.fakes.catalog_seed import seed_action_types, seed_catalog
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.support.database import rolled_back_session
from tests.support.user_ids import OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from datetime import datetime

    from sqlalchemy.engine import URL

    from app.domain.bant.entities import BantLabel
    from app.domain.bant.values import BantCategory
    from app.domain.contact.entities import Contact
    from app.domain.contact.values import ContactId
    from app.domain.deal.code import DealCode
    from app.domain.deal.entities import Deal
    from app.domain.deal_action.entities import DealAction
    from app.domain.user.value_objects import UserId
    from app.domain.vendor.entities import Vendor

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@dataclass
class DealCase:
    deals: Any
    history: Any
    actions: Any
    contacts: Any
    users: Any
    codes: Any
    labels: Any
    vendors: Any
    action_type_source: Callable[[], Any] | None = None
    _action_types: Any = field(default=None, repr=False)

    @property
    def action_types(self) -> Any:  # noqa: ANN401 - ActionTypeRepository(Fake 또는 SQL)
        """Action 유형 저장소. 처음 쓸 때 만든다(Action을 다루지 않는 테스트가 유형 도메인 모듈을
        가져오지 않게 한다. Fake는 이때 기본 유형 8개를 시드한다)."""
        if self._action_types is None:
            assert self.action_type_source is not None, "이 case는 Action 유형을 지원하지 않는다"
            self._action_types = self.action_type_source()
        return self._action_types

    async def _ensure_contact(self, contact_id: ContactId, kind: ContactKind) -> None:
        try:
            await self.contacts.get(contact_id)
        except ContactNotFoundError:
            await self.contacts.add(make_contact(kind, entity_id=contact_id))

    async def ensure_owner(self, user_id: UserId = OWNER_ID) -> None:
        await ensure_users(self.users, user_id)

    async def add(self, deal: Deal) -> None:
        """Deal이 참조하는 담당자·고객·파트너 행을 (없으면) 만든 뒤 저장한다."""
        await self.ensure_owner(deal.details.owner_user_id)
        await self._ensure_contact(deal.customer_id, ContactKind.CUSTOMER)
        for link in deal.partner_links:
            await self._ensure_contact(link.contact_id, ContactKind.PARTNER)
        await self.deals.add(deal)

    async def new_contact(
        self,
        kind: ContactKind = ContactKind.CUSTOMER,
        **overrides: Any,  # noqa: ANN401 - 팩토리 필드를 그대로 넘긴다
    ) -> Contact:
        contact = make_contact(kind, **overrides)
        await self.contacts.add(contact)
        return contact

    async def new_label(self, category: BantCategory, name: str) -> BantLabel:
        label = make_label(category, name=name)
        await self.labels.add(label)
        return label

    async def new_vendor(self, name: str) -> Vendor:
        """Vendor를 저장한다(Deal이 고를 수 있는 선택지)."""
        return await store_vendor(self.vendors, name)

    async def add_action(
        self,
        deal: Deal,
        acted_at: datetime = NOW,
        **overrides: Any,  # noqa: ANN401 - 팩토리 필드를 그대로 넘긴다
    ) -> DealAction:
        """Deal에 활동 한 건을 저장한다(활동자 행도 만든다).

        유형은 이 저장소의 같은 이름 유형으로 맞춘다(`attach_catalog_type`: DB 시드 id는 무작위).
        """
        action = make_deal_action(deal_code=deal.id, acted_at=acted_at, **overrides)
        await attach_catalog_type(self.action_types, action)
        await ensure_users(self.users, action.actor_user_id)
        await self.actions.add(action)
        return action

    async def set_next_action_status(
        self, action: DealAction, status: str, at: datetime, note: str = ""
    ) -> None:
        """저장된 Action의 Next Action 상태를 바꿔 저장한다(도메인 메서드 + Port의 update)."""
        from app.domain.deal_action.next_action_status import NextActionStatus  # noqa: PLC0415

        action.change_next_action_status(NextActionStatus(status), note, at)
        await self.actions.update(action)

    async def revise(self, code: DealCode, **parts: object) -> None:
        """저장된 Deal의 폼 값(details, sync, customer_id, bant) 일부를 바꿔 저장한다."""
        deal = await self.deals.get(code)
        values: dict[str, Any] = {
            "details": deal.details,
            "sync": deal.sync,
            "customer_id": deal.customer_id,
            "bant": deal.bant,
            **parts,
        }
        deal.revise(**values)
        await self.deals.update(deal)

    async def replace_partner(
        self, code: DealCode, contact_id: ContactId | None, at: datetime
    ) -> None:
        deal = await self.deals.get(code)
        deal.replace_partner(contact_id, at)
        await self.deals.update(deal)

    async def actions_of(self, code: DealCode) -> list[DealAction]:
        """그 Deal의 Action 전부(전역 검색은 폐지되어 Deal 단위로만 읽는다)."""
        return list(await self.actions.search(DealActionQuery(deal_code=code)))

    async def resign(self, user_id: UserId, at: datetime) -> None:
        user = await self.users.get(user_id)
        user.resign(at)
        await self.users.update(user)


def _seeded_types(uow: FakeUnitOfWork) -> Any:  # noqa: ANN401
    seed_action_types(uow)
    return uow.action_types


def _fake_case() -> DealCase:
    uow = FakeUnitOfWork()
    seed_catalog(uow)
    return DealCase(
        uow.deals,
        uow.deal_history,
        uow.deal_actions,
        uow.contacts,
        uow.users,
        uow.codes,
        uow.bant_labels,
        uow.vendors,
        lambda: _seeded_types(uow),
    )


def _sql_types(session: Any) -> Any:  # noqa: ANN401
    from app.infra.db.action_type_repository import SqlActionTypeRepository  # noqa: PLC0415

    return SqlActionTypeRepository(session)


def _sql_case(session: Any) -> DealCase:  # noqa: ANN401

    from app.infra.db.bant_label_repository import SqlBantLabelRepository  # noqa: PLC0415
    from app.infra.db.code_repository import SqlCodeRepository  # noqa: PLC0415
    from app.infra.db.contact_repository import SqlContactRepository  # noqa: PLC0415
    from app.infra.db.deal_action_repository import SqlDealActionRepository  # noqa: PLC0415
    from app.infra.db.deal_history_repository import SqlDealHistoryRepository  # noqa: PLC0415
    from app.infra.db.deal_repository import SqlDealRepository  # noqa: PLC0415
    from app.infra.db.user_repository import SqlUserRepository  # noqa: PLC0415
    from app.infra.db.vendor_repository import SqlVendorRepository  # noqa: PLC0415

    return DealCase(
        SqlDealRepository(session),
        SqlDealHistoryRepository(session),
        SqlDealActionRepository(session),
        SqlContactRepository(session),
        SqlUserRepository(session),
        SqlCodeRepository(session),
        SqlBantLabelRepository(session),
        SqlVendorRepository(session),
        lambda: _sql_types(session),
    )


@asynccontextmanager
async def open_deal_case(
    implementation: str, test_database_url: URL | None
) -> AsyncIterator[DealCase]:
    if implementation == "fake":
        yield _fake_case()
        return
    async with rolled_back_session(test_database_url) as session:  # type: ignore[arg-type]
        yield _sql_case(session)
