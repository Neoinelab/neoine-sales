"""ActionTypeRepository Port의 구현체 적합성과 UoW·Provider 노출을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.action_type_repository import ActionTypeRepository
from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.action_type_repository import SqlActionTypeRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.action_types import FakeActionTypeRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases

PORT_METHODS = ("list", "get", "add", "update", "delete")
ACTION_TYPE_USE_CASES = (
    "list_action_types",
    "register_action_type",
    "rename_action_type",
    "delete_action_type",
)


def test_action_type_repositories_satisfy_the_port() -> None:
    """Fake와 SQL 구현은 Port의 비동기 메서드를 모두 가진다."""
    # given: 접속하지 않는 엔진 위의 SQL 저장소와 Fake 저장소
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: ActionTypeRepository = FakeActionTypeRepository()
    sql: ActionTypeRepository = SqlActionTypeRepository(AsyncSession(engine))

    # when·then: 두 구현의 Port 메서드가 모두 코루틴 함수이고 Port에도 있다
    assert fake is not None
    assert sql is not None
    for name in PORT_METHODS:
        assert inspect.iscoroutinefunction(getattr(SqlActionTypeRepository, name)), name
        assert inspect.iscoroutinefunction(getattr(FakeActionTypeRepository, name)), name
        assert hasattr(ActionTypeRepository, name), name


def test_unit_of_work_port_and_implementations_expose_action_types() -> None:
    """UoW Port와 구현들은 action_types 저장소를 노출한다."""
    # given: Fake UoW
    fake = FakeUnitOfWork()

    # when·then: Port·Fake·SQL UoW가 action_types를 노출한다
    assert hasattr(UnitOfWork, "action_types")
    assert isinstance(fake.action_types, FakeActionTypeRepository)
    assert "action_types" in SqlUnitOfWork.__annotations__


def test_the_web_port_exposes_the_action_type_use_cases() -> None:
    """web Port와 구현들은 Action 유형 유스케이스를 노출한다."""
    # when·then: Provider·Fake·Container가 네 유스케이스를 모두 가진다
    for name in ACTION_TYPE_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
