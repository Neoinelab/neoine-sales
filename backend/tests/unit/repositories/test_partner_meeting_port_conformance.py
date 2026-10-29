"""파트너 미팅 Port의 구현체 적합성과 UoW·Provider 노출을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from app.application.ports.partner_meeting_repository import PartnerMeetingRepository
from app.infra.db.partner_meeting_repository import SqlPartnerMeetingRepository
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.partner_meetings import FakePartnerMeetingRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases

PORT_METHODS = ("add", "get", "update", "delete", "search", "count", "deal_choices")
MEETING_USE_CASES = (
    "register_partner_meetings",
    "update_partner_meeting",
    "delete_partner_meeting",
    "list_partner_meetings",
    "list_partner_deal_choices",
)


def test_meeting_repositories_satisfy_the_port() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: PartnerMeetingRepository = FakePartnerMeetingRepository()
    sql: PartnerMeetingRepository = SqlPartnerMeetingRepository(AsyncSession(engine))

    assert fake is not None
    assert sql is not None
    for name in PORT_METHODS:
        assert inspect.iscoroutinefunction(getattr(SqlPartnerMeetingRepository, name)), name
        assert inspect.iscoroutinefunction(getattr(FakePartnerMeetingRepository, name)), name
        assert hasattr(PartnerMeetingRepository, name), name


def test_unit_of_work_port_and_implementations_expose_partner_meetings() -> None:
    fake = FakeUnitOfWork()

    assert hasattr(UnitOfWork, "partner_meetings")
    assert isinstance(fake.partner_meetings, FakePartnerMeetingRepository)
    assert "partner_meetings" in SqlUnitOfWork.__annotations__


def test_the_web_port_exposes_the_partner_meeting_use_cases() -> None:
    for name in MEETING_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
