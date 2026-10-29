"""PartnerMeetingRepository 계약 테스트 공용 case(Fake와 SQL 구현 양쪽).

미팅은 Deal(code)·작성자(users) 아래에 있고, Deal은 고객·파트너 연락처를 가진다. 그래서 case는
`DealCase`(Deal·연락처·사용자 저장소)와 미팅 저장소를 함께 들고, 필요한 행을 먼저 만든다. Fake는
`FakeUnitOfWork`가 연결한(FK 모사) 저장소를 쓰고 SQL은 한 세션 위의 Sql 저장소들을 쓴다.
회사명·담당자명은
공백 금지 규칙이 있다(연락처 값 규칙). SQL 구현 모듈은 사용 시점에 가져온다.
"""

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest

from app.domain.contact.values import ContactKind
from app.domain.user.errors import UserNotFoundError
from tests.factories import NOW, make_deal, make_deal_code
from tests.factories_auth import make_user
from tests.factories_partner_meeting import make_meeting
from tests.fakes.catalog_seed import seed_catalog
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.support.database import rolled_back_session
from tests.support.user_ids import login_of
from tests.support.user_seed import ensure_users
from tests.unit.repositories.deal_case import DealCase

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.partner_meeting_repository import (
        PartnerMeetingRecord,
        PartnerMeetingRepository,
    )
    from app.domain.partner_meeting.entities import PartnerMeeting
    from sqlalchemy.engine import URL

    from app.domain.contact.entities import Contact
    from app.domain.deal.code import DealCode
    from app.domain.user.value_objects import UserId

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]
HANBIT = "한빛파트너스"


class MeetingCase:
    def __init__(self, deal_case: DealCase, meetings: PartnerMeetingRepository) -> None:
        self._deal_case = deal_case
        self.repository = meetings
        self.deals = deal_case.deals
        self.contacts = deal_case.contacts
        self.users = deal_case.users
        self._count = 0

    def _next(self) -> int:
        self._count += 1
        return self._count

    async def partner(self, company: str = HANBIT, name: str | None = None) -> Contact:
        n = self._next()
        return await self._deal_case.new_contact(
            ContactKind.PARTNER,
            company=company,
            name=name or f"담당자{n}",
            email=f"p{n}@partner.test",
        )

    async def deal(  # noqa: PLR0913 - Deal 준비에 필요한 독립적인 선택지
        self,
        *,
        name: str = "ERP 구축",
        partner: Contact | None = None,
        company: str | None = HANBIT,
        customer_company: str = "네오인",
        forecast_key: str = "pipeline",
        status_key: str = "prospecting",
    ) -> DealCode:
        """Deal 한 건(활성 파트너는 partner, 생략하면 company의 새 담당자, None이면 파트너 없음)."""
        n = self._next()
        code = make_deal_code(f"M{n:03d}")
        customer = await self._deal_case.new_contact(
            ContactKind.CUSTOMER,
            company=customer_company,
            name=f"고객{n}",
            email=f"c{n}@customer.test",
        )
        linked = partner
        if linked is None and company is not None:
            linked = await self.partner(company)
        await self._deal_case.add(
            make_deal(
                code=code,
                name=name,
                customer_id=customer.id,
                partner_id=None if linked is None else linked.id,
                forecast_key=forecast_key,
                status_key=status_key,
            )
        )
        return code

    async def rename_deal(self, code: DealCode, name: str) -> None:
        deal = await self.deals.get(code)
        await self._deal_case.revise(code, details=replace(deal.details, name=name))

    async def unlink(self, code: DealCode) -> None:
        await self._deal_case.replace_partner(code, None, NOW + timedelta(days=1))

    async def relink(self, code: DealCode, contact: Contact) -> None:
        await self._deal_case.replace_partner(code, contact.id, NOW + timedelta(days=2))

    async def author(
        self, user_id: UserId, display_name: str | None = None, *, login_id: str | None = None
    ) -> UserId:
        """작성자 행을 표시 이름(비어 있으면 None)과 함께 만든다. 이미 있으면 건드리지 않는다."""
        try:
            await self.users.get(user_id)
        except UserNotFoundError:
            await self.users.add(
                make_user(
                    login_id or login_of(user_id), entity_id=user_id, display_name=display_name
                )
            )
        return user_id

    async def resign(self, user_id: UserId) -> None:
        await self._deal_case.resign(user_id, NOW + timedelta(days=30))

    async def add(self, meeting: PartnerMeeting) -> PartnerMeeting:
        """작성자 행을 (없으면) 만들고 저장한다. Deal은 먼저 `deal()`로 만들어 둔다."""
        await ensure_users(self.users, meeting.author_user_id)
        await self.repository.add(meeting)
        return meeting

    async def add_many(self, code: DealCode, *contents: str, company: str = HANBIT) -> list[Any]:
        """내용마다 미팅 하나(날짜는 기본 하루 간격으로 늘어난다)."""
        made = []
        for offset, content in enumerate(contents):
            made.append(
                await self.add(
                    make_meeting(
                        deal_code=code,
                        company=company,
                        content=content,
                        meeting_date=NOW.date() + timedelta(days=offset),
                    )
                )
            )
        return made

    async def found(self, **criteria: Any) -> list[PartnerMeetingRecord]:  # noqa: ANN401
        from app.application.ports.partner_meeting_repository import (  # noqa: PLC0415
            PartnerMeetingQuery,
        )

        return list(await self.repository.search(PartnerMeetingQuery(**criteria)))

    async def contents(self, **criteria: Any) -> list[str]:  # noqa: ANN401
        """검색 결과의 미팅 내용(정렬 순서 그대로)."""
        return [r.meeting.content.value for r in await self.found(**criteria)]

    async def total(self, **criteria: Any) -> int:  # noqa: ANN401
        from app.application.ports.partner_meeting_repository import (  # noqa: PLC0415
            PartnerMeetingQuery,
        )

        return await self.repository.count(PartnerMeetingQuery(**criteria))


def _fake_case() -> MeetingCase:
    uow = FakeUnitOfWork()
    seed_catalog(uow)
    deal_case = DealCase(
        uow.deals,
        uow.deal_history,
        uow.deal_actions,
        uow.contacts,
        uow.users,
        uow.codes,
        uow.bant_labels,
        uow.vendors,
    )
    return MeetingCase(deal_case, uow.partner_meetings)


def _sql_case(session: Any) -> MeetingCase:  # noqa: ANN401
    from app.infra.db.partner_meeting_repository import (  # noqa: PLC0415
        SqlPartnerMeetingRepository,
    )

    from app.infra.db.bant_label_repository import SqlBantLabelRepository  # noqa: PLC0415
    from app.infra.db.code_repository import SqlCodeRepository  # noqa: PLC0415
    from app.infra.db.contact_repository import SqlContactRepository  # noqa: PLC0415
    from app.infra.db.deal_action_repository import SqlDealActionRepository  # noqa: PLC0415
    from app.infra.db.deal_history_repository import SqlDealHistoryRepository  # noqa: PLC0415
    from app.infra.db.deal_repository import SqlDealRepository  # noqa: PLC0415
    from app.infra.db.user_repository import SqlUserRepository  # noqa: PLC0415
    from app.infra.db.vendor_repository import SqlVendorRepository  # noqa: PLC0415

    deal_case = DealCase(
        SqlDealRepository(session),
        SqlDealHistoryRepository(session),
        SqlDealActionRepository(session),
        SqlContactRepository(session),
        SqlUserRepository(session),
        SqlCodeRepository(session),
        SqlBantLabelRepository(session),
        SqlVendorRepository(session),
    )
    return MeetingCase(deal_case, SqlPartnerMeetingRepository(session))


@asynccontextmanager
async def open_meeting_case(
    implementation: str, test_database_url: URL | None
) -> AsyncIterator[MeetingCase]:
    if implementation == "fake":
        yield _fake_case()
        return
    async with rolled_back_session(test_database_url) as session:  # type: ignore[arg-type]
        yield _sql_case(session)
