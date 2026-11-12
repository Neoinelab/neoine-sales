"""파트너 미팅 Port의 구현체 적합성과 UoW·Provider 노출을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.partner_meeting_repository import PartnerMeetingRepository
from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.partner_meeting_repository import SqlPartnerMeetingRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.partner_meetings import FakePartnerMeetingRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases

PORT_METHODS = ("add", "get", "update", "delete", "search", "count")
MEETING_USE_CASES = (
    "register_partner_meetings",
    "update_partner_meeting",
    "delete_partner_meeting",
    "list_partner_meetings",
)


def test_meeting_repositories_satisfy_the_port() -> None:
    """Fake와 SQL 구현이 Port의 비동기 메서드를 모두 갖는다."""
    # given: 접속하지 않는 엔진 위의 Fake와 SQL 구현
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: PartnerMeetingRepository = FakePartnerMeetingRepository()
    sql: PartnerMeetingRepository = SqlPartnerMeetingRepository(AsyncSession(engine))
    # when·then: Port의 각 메서드가 두 구현에서 코루틴 함수다
    assert fake is not None
    assert sql is not None
    for name in PORT_METHODS:
        assert inspect.iscoroutinefunction(getattr(SqlPartnerMeetingRepository, name)), name
        assert inspect.iscoroutinefunction(getattr(FakePartnerMeetingRepository, name)), name
        assert hasattr(PartnerMeetingRepository, name), name


def test_the_port_has_no_deal_choices_method() -> None:
    """Port와 구현·Provider에 Deal 선택지 메서드가 없다."""
    # when·then: Port·Fake·SQL 구현·Provider를 살피면 deal_choices가 어디에도 없다
    assert not hasattr(PartnerMeetingRepository, "deal_choices")
    assert not hasattr(FakePartnerMeetingRepository, "deal_choices")
    assert not hasattr(SqlPartnerMeetingRepository, "deal_choices")
    assert not hasattr(UseCaseProvider, "list_partner_deal_choices")


def test_unit_of_work_port_and_implementations_expose_partner_meetings() -> None:
    """UoW Port와 구현이 partner_meetings를 노출한다."""
    # given: Fake UoW
    fake = FakeUnitOfWork()
    # when·then: Port와 구현이 partner_meetings를 갖는다
    assert hasattr(UnitOfWork, "partner_meetings")
    assert isinstance(fake.partner_meetings, FakePartnerMeetingRepository)
    assert "partner_meetings" in SqlUnitOfWork.__annotations__


def test_the_web_port_exposes_the_partner_meeting_use_cases() -> None:
    """웹 Port와 Fake·Container가 미팅 유스케이스 넷을 노출한다."""
    # when·then: 네 유스케이스 이름이 Provider·Fake·Container에 있다
    for name in MEETING_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
