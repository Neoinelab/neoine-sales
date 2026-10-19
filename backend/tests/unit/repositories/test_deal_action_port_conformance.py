"""Action 저장소·유스케이스가 Port와 일치하고 폐지된 전역 검색이 없는지 확인한다(P2)."""

from dataclasses import fields

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.deal_action_repository import DealActionQuery, DealActionRepository
from app.container import Container
from app.infra.db.deal_action_repository import SqlDealActionRepository
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.repositories import FakeDealActionRepository
from tests.fakes.use_cases import FakeUseCases

ACTION_PORT_METHODS = (
    "add",
    "get",
    "search",
    "update",
    "delete",
    "count_by_code",
    "count_by_action_type",
)
ACTION_USE_CASES = (
    "register_deal_action",
    "get_deal_action",
    "list_deal_actions",
    "update_deal_action",
    "delete_deal_action",
)


def test_fake_and_sql_action_repositories_satisfy_the_port() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: DealActionRepository = FakeDealActionRepository()
    sql: DealActionRepository = SqlDealActionRepository(AsyncSession(engine))

    assert fake is not None
    assert sql is not None


def test_action_repositories_expose_every_port_method() -> None:
    for repository_type in (FakeDealActionRepository, SqlDealActionRepository):
        for name in ACTION_PORT_METHODS:
            assert callable(getattr(repository_type, name)), (repository_type, name)
    for name in ACTION_PORT_METHODS:
        assert hasattr(DealActionRepository, name), name


def test_the_query_has_no_paging_fields() -> None:
    names = {f.name for f in fields(DealActionQuery)}

    assert "deal_code" in names
    assert not {"offset", "limit"} & names


def test_the_query_filters_by_type_id_and_no_longer_by_the_enum() -> None:
    names = {f.name for f in fields(DealActionQuery)}

    assert "action_type_id" in names
    assert "action_type" not in names


def test_the_web_port_exposes_the_action_use_cases_and_not_the_global_search() -> None:
    for name in ACTION_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
    for retired in ("search_deal_actions",):
        assert not hasattr(UseCaseProvider, retired), retired
        assert not hasattr(FakeUseCases, retired), retired
        assert not hasattr(Container, retired), retired
