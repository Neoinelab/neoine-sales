"""Deal Comment Port의 구현체 적합성과 UoW·Provider 노출을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.deal_comment_repository import DealCommentRepository
from app.application.ports.id_allocator import IdKind
from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.deal_comment_repository import SqlDealCommentRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.deal_comments import FakeDealCommentRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases

PORT_METHODS = (
    "add",
    "get",
    "list_for_deal",
    "mark_read",
    "unread_counts",
    "delete",
    "count_for_action",
)
COMMENT_USE_CASES = (
    "write_deal_comment",
    "list_deal_comments",
    "get_deal_comment",
    "delete_deal_comment",
    "mark_deal_comments_read",
    "count_unread_deal_comments",
)


def test_comment_repositories_satisfy_the_port() -> None:
    """Fake와 SQL 구현이 Port의 비동기 메서드를 모두 갖는다.

    테스트 코드: CM-001
    """
    # given: 접속하지 않는 엔진 위의 Fake와 SQL 구현
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: DealCommentRepository = FakeDealCommentRepository()
    sql: DealCommentRepository = SqlDealCommentRepository(AsyncSession(engine))
    # when·then: Port의 각 메서드가 두 구현에서 코루틴 함수다
    assert fake is not None
    assert sql is not None
    for name in PORT_METHODS:
        assert inspect.iscoroutinefunction(getattr(SqlDealCommentRepository, name)), name
        assert inspect.iscoroutinefunction(getattr(FakeDealCommentRepository, name)), name
        assert hasattr(DealCommentRepository, name), name


def test_unit_of_work_port_and_implementations_expose_deal_comments() -> None:
    """UoW Port와 구현이 deal_comments를 노출한다."""
    # given: Fake UoW
    fake = FakeUnitOfWork()
    # when·then: Port와 구현이 deal_comments를 갖는다
    assert hasattr(UnitOfWork, "deal_comments")
    assert isinstance(fake.deal_comments, FakeDealCommentRepository)
    assert "deal_comments" in SqlUnitOfWork.__annotations__


def test_the_id_allocator_numbers_comments_as_their_own_kind() -> None:
    """앱이 직접 번호를 받는 종류에 deal_comment가 있다.

    테스트 코드: CM-001
    """
    # when·then: 새 종류의 값이 deal_comment다
    assert IdKind.DEAL_COMMENT.value == "deal_comment"


def test_the_repository_port_has_no_update_and_no_edit_use_case() -> None:
    """수정이 폐지되어 Port에 update가 없고 웹 Port·Fake에 update_deal_comment가 없다.

    테스트 코드: CM-057
    """
    # when·then: 수정 관련 이름이 어디에도 없다
    assert not hasattr(DealCommentRepository, "update")
    assert not hasattr(FakeDealCommentRepository, "update")
    assert not hasattr(SqlDealCommentRepository, "update")
    assert not hasattr(UseCaseProvider, "update_deal_comment")
    assert not hasattr(Container, "update_deal_comment")


def test_the_web_port_exposes_the_comment_use_cases() -> None:
    """웹 Port와 Fake·Container가 Comment 유스케이스 여섯을 노출한다."""
    # when·then: 여섯 유스케이스 이름이 Provider·Fake·Container에 있다
    for name in COMMENT_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
