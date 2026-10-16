"""P2b R2 Port(AttachmentRepository)의 구현체 적합성과 UoW·유스케이스 공급자 노출을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from app.application.ports.attachment_repository import AttachmentRepository
from app.infra.db.attachment_repository import SqlAttachmentRepository
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.file_storage import StorageNotReadableError
from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.attachments import FakeAttachmentRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases

ATTACHMENT_METHODS = ("add", "get", "find_by_name", "list_by_deal", "update", "delete")
ATTACHMENT_USE_CASES = (
    "list_attachments",
    "get_attachment",
    "upload_attachment",
    "delete_attachment",
    "download_attachment",
)


def test_attachment_repositories_satisfy_the_port() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: AttachmentRepository = FakeAttachmentRepository()
    sql: AttachmentRepository = SqlAttachmentRepository(AsyncSession(engine))

    assert fake is not None
    assert sql is not None


def test_every_attachment_repository_method_is_a_coroutine_on_both_implementations() -> None:
    for name in ATTACHMENT_METHODS:
        assert hasattr(AttachmentRepository, name), name
        assert inspect.iscoroutinefunction(getattr(FakeAttachmentRepository, name)), name
        assert inspect.iscoroutinefunction(getattr(SqlAttachmentRepository, name)), name


def test_unit_of_work_port_and_implementations_expose_attachments() -> None:
    fake = FakeUnitOfWork()

    assert hasattr(UnitOfWork, "attachments")
    assert isinstance(fake.attachments, FakeAttachmentRepository)
    assert "attachments" in SqlUnitOfWork.__annotations__


def test_the_web_port_exposes_the_attachment_use_cases() -> None:
    for name in ATTACHMENT_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name


def test_the_file_storage_port_names_a_read_failure_error() -> None:
    assert issubclass(StorageNotReadableError, Exception)
