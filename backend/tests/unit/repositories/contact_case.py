"""ContactRepository 계약 테스트 공용 case(Fake와 SQL 구현 양쪽).

한 case는 연락처 저장소와, 연락처를 참조하는 Deal 저장소·그 담당자 사용자 저장소를 함께 가진다.
SQL 구현은 사용 시점에 가져와, 구현 전에도 이 모듈을 쓰는 다른 계약 테스트의 수집이 막히지 않게
한다. 테스트마다 롤백되는 세션을 쓰므로 SQL 쪽도 비어 있는 contacts 표에서 시작한다.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from tests.factories import make_deal
from tests.fakes.contacts import FakeContactRepository
from tests.fakes.repositories import FakeDealRepository
from tests.fakes.user_repository import FakeUserRepository
from tests.support.database import rolled_back_session
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL

    from app.application.ports.contact_repository import ContactRepository
    from app.application.ports.deal_repository import DealRepository
    from app.application.ports.user_repository import UserRepository
    from app.domain.contact.entities import Contact
    from app.domain.deal.entities import Deal

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@dataclass
class ContactCase:
    """한 구현(fake 또는 sql)의 연락처 저장소. Port 계약만 보고 쓴다."""

    contacts: ContactRepository
    deals: DealRepository
    users: UserRepository

    async def add_all(self, *contacts: Contact) -> None:
        for contact in contacts:
            await self.contacts.add(contact)

    async def add_deal(
        self, customer: Contact, partner: Contact | None = None, *, code: str | None = None
    ) -> Deal:
        """customer(와 partner)를 참조하는 Deal 1건을 저장한다(담당자 행은 필요하면 만든다)."""
        deal = make_deal(
            customer_id=customer.id,
            partner_id=partner.id if partner else None,
            code=code or f"20261016-{format(customer.id % 0xFFFF, '04X')}",
        )
        await ensure_users(self.users, deal.details.owner_user_id)
        await self.deals.add(deal)
        return deal


@asynccontextmanager
async def open_contacts(
    implementation: str, test_database_url: URL | None
) -> AsyncIterator[ContactCase]:
    if implementation == "fake":
        contacts, deals = FakeContactRepository(), FakeDealRepository()
        contacts.restrict_delete_by(deals)  # FK RESTRICT 모사
        yield ContactCase(contacts, deals, FakeUserRepository())
        return
    from app.infra.db.contact_repository import SqlContactRepository  # noqa: PLC0415
    from app.infra.db.deal_repository import SqlDealRepository  # noqa: PLC0415
    from app.infra.db.user_repository import SqlUserRepository  # noqa: PLC0415

    async with rolled_back_session(test_database_url) as session:  # type: ignore[arg-type]
        yield ContactCase(
            SqlContactRepository(session), SqlDealRepository(session), SqlUserRepository(session)
        )
