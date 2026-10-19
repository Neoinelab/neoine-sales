"""AttachmentRepository 계약 테스트 공용 case(Fake와 SQL 구현 양쪽, P2b R2).

첨부는 Deal(code) 아래에 있고 업로더(users)를 FK로 참조하므로, case가 필요한 Deal·업로더 행을 먼저
만든다. 저장소 준비는 `deal_case.py`와 같다(Fake는 `FakeUnitOfWork`가 연결한 저장소, SQL은
한 세션 위의 Sql 저장소). SQL 구현 모듈은 사용 시점에 가져온다.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest

from tests.factories import make_deal, make_deal_code
from tests.fakes.catalog_seed import seed_catalog
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.support.database import rolled_back_session
from tests.support.user_seed import ensure_users
from tests.unit.repositories.deal_case import DealCase, _sql_case

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL

    from app.application.ports.attachment_repository import AttachmentRepository
    from app.domain.attachment.entities import Attachment
    from app.domain.deal.code import DealCode

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


class AttachmentCase:
    def __init__(self, deal_case: DealCase, repository: AttachmentRepository) -> None:
        self._deal_case = deal_case
        self.repository = repository
        self.deals = deal_case.deals
        self.users = deal_case.users

    async def ensure_deal(self, code: DealCode) -> None:
        if not await self.deals.exists(code):
            await self._deal_case.add(make_deal(code=code))

    async def add(self, attachment: Attachment) -> None:
        """Deal과 업로더 행을 (없으면) 만든 뒤 첨부를 저장한다."""
        await self.ensure_deal(attachment.deal_code)
        await ensure_users(self.users, attachment.uploaded_by)
        await self.repository.add(attachment)

    async def names(self, code: DealCode | None = None) -> list[str]:
        """그 Deal 첨부의 파일 이름(목록 순서 그대로)."""
        found = await self.repository.list_by_deal(code or make_deal_code())
        return [a.file_name.value for a in found]


@asynccontextmanager
async def open_attachment_case(
    implementation: str, test_database_url: URL | None
) -> AsyncIterator[AttachmentCase]:
    if implementation == "fake":
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
        yield AttachmentCase(deal_case, uow.attachments)
        return
    from app.infra.db.attachment_repository import SqlAttachmentRepository  # noqa: PLC0415

    async with rolled_back_session(test_database_url) as session:  # type: ignore[arg-type]
        yield AttachmentCase(_sql_case(session), SqlAttachmentRepository(session))
