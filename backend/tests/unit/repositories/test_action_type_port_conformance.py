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
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: ActionTypeRepository = FakeActionTypeRepository()
    sql: ActionTypeRepository = SqlActionTypeRepository(AsyncSession(engine))

    assert fake is not None
    assert sql is not None
    for name in PORT_METHODS:
        assert inspect.iscoroutinefunction(getattr(SqlActionTypeRepository, name)), name
        assert inspect.iscoroutinefunction(getattr(FakeActionTypeRepository, name)), name
        assert hasattr(ActionTypeRepository, name), name


def test_unit_of_work_port_and_implementations_expose_action_types() -> None:
    fake = FakeUnitOfWork()

    assert hasattr(UnitOfWork, "action_types")
    assert isinstance(fake.action_types, FakeActionTypeRepository)
    assert "action_types" in SqlUnitOfWork.__annotations__


def test_the_web_port_exposes_the_action_type_use_cases() -> None:
    for name in ACTION_TYPE_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
