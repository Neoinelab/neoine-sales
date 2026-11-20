"""Action 저장소·유스케이스가 Port와 일치하고 폐지된 전역 검색이 없는지 확인한다."""

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
    "next_action_basis",
)
ACTION_USE_CASES = (
    "register_deal_action",
    "get_deal_action",
    "list_deal_actions",
    "update_deal_action",
    "delete_deal_action",
    "change_next_action_status",
)


def test_fake_and_sql_action_repositories_satisfy_the_port() -> None:
    """Fake와 SQL Action 저장소가 모두 Port 타입으로 만들어진다."""
    # given: 접속하지 않는 엔진
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    # when: 두 구현체를 Port 타입으로 만든다
    fake: DealActionRepository = FakeDealActionRepository()
    sql: DealActionRepository = SqlDealActionRepository(AsyncSession(engine))

    # then: 둘 다 만들어진다
    assert fake is not None
    assert sql is not None


def test_action_repositories_expose_every_port_method() -> None:
    """두 구현체와 Port 모두 Port 메서드를 갖는다."""
    # when: 구현체와 Port의 메서드를 훑는다
    for repository_type in (FakeDealActionRepository, SqlDealActionRepository):
        for name in ACTION_PORT_METHODS:
            # then: 두 구현체의 메서드가 모두 호출 가능하다
            assert callable(getattr(repository_type, name)), (repository_type, name)
    for name in ACTION_PORT_METHODS:
        # then: Port에도 그 메서드가 있다
        assert hasattr(DealActionRepository, name), name


def test_the_query_has_no_paging_fields() -> None:
    """Action 검색 조건에는 쪽 나누기 필드가 없다."""
    # when: 검색 조건의 필드 이름을 읽는다
    names = {f.name for f in fields(DealActionQuery)}

    # then: Deal 코드는 있고 offset·limit은 없다
    assert "deal_code" in names
    assert not {"offset", "limit"} & names


def test_the_query_filters_by_type_id_and_no_longer_by_the_enum() -> None:
    """Action 검색 조건은 유형 id를 쓰고 예전 enum 필드는 없다."""
    # when: 검색 조건의 필드 이름을 읽는다
    names = {f.name for f in fields(DealActionQuery)}

    # then: action_type_id는 있고 action_type은 없다
    assert "action_type_id" in names
    assert "action_type" not in names


def test_the_web_port_exposes_the_action_use_cases_and_not_the_global_search() -> None:
    """웹 Port는 Action 유스케이스를 노출하고 폐지된 전역 검색은 없다."""
    # when: 유스케이스 공급자·Fake·조립체를 훑는다
    for name in ACTION_USE_CASES:
        # then: 세 곳 모두 Action 유스케이스가 있다
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
    # when: 폐지된 전역 검색을 훑는다
    for retired in ("search_deal_actions",):
        # then: 세 곳 모두 없다
        assert not hasattr(UseCaseProvider, retired), retired
        assert not hasattr(FakeUseCases, retired), retired
        assert not hasattr(Container, retired), retired


def test_the_queries_carry_an_optional_next_action_status_filter() -> None:
    """Action·Deal 검색 조건 모두 선택적 Next Action 상태 필터를 갖는다."""
    # given: Deal 검색 조건 타입
    from app.application.ports.deal_repository import DealQuery  # noqa: PLC0415

    # when: 두 검색 조건의 필드 이름을 읽는다
    for query_type in (DealActionQuery, DealQuery):
        names = {f.name for f in fields(query_type)}
        # then: 둘 다 상태 필터 필드가 있다
        assert "next_action_status" in names, query_type
    # then: Deal 검색 조건의 기본값은 필터 없음이다
    assert DealQuery().next_action_status is None
