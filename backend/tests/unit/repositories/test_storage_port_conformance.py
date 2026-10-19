"""P2b R1 Port(FileStorage, StorageSettingsRepository)의 구현체 적합성을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.file_storage import FileStorage, OpenedFile, StoredFileLocation
from app.application.ports.storage_settings_repository import StorageSettingsRepository
from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.storage_settings_repository import SqlStorageSettingsRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.infra.storage.local_file_storage import LocalFileStorage
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.file_storage import FakeFileStorage
from tests.fakes.storage_settings_repository import FakeStorageSettingsRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases

FILE_STORAGE_METHODS = ("check_writable", "save", "open", "delete", "delete_deal_files")
STORAGE_USE_CASES = (
    "register_setup_storage",
    "test_setup_storage",
    "get_storage_settings",
    "update_storage_settings",
    "test_storage_settings",
)


def test_file_storage_implementations_satisfy_the_port() -> None:
    fake: FileStorage = FakeFileStorage()
    local: FileStorage = LocalFileStorage()

    assert fake is not None
    assert local is not None


def test_file_storage_implementations_expose_every_port_method_as_a_coroutine() -> None:
    for implementation in (FakeFileStorage, LocalFileStorage):
        for name in FILE_STORAGE_METHODS:
            assert inspect.iscoroutinefunction(getattr(implementation, name)), (
                implementation,
                name,
            )
    for name in FILE_STORAGE_METHODS:
        assert hasattr(FileStorage, name), name


def test_the_file_storage_port_carries_a_location_and_an_opened_file_value() -> None:
    assert {"deal_code", "key"} <= set(StoredFileLocation.__dataclass_fields__)
    assert {"size", "chunks"} <= set(OpenedFile.__dataclass_fields__)


def test_storage_settings_repositories_satisfy_the_port() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: StorageSettingsRepository = FakeStorageSettingsRepository()
    sql: StorageSettingsRepository = SqlStorageSettingsRepository(AsyncSession(engine))

    assert fake is not None
    assert sql is not None
    for name in ("get", "save"):
        assert inspect.iscoroutinefunction(getattr(SqlStorageSettingsRepository, name))
        assert inspect.iscoroutinefunction(getattr(FakeStorageSettingsRepository, name))
        assert hasattr(StorageSettingsRepository, name)


def test_unit_of_work_port_and_implementations_expose_storage_settings() -> None:
    fake = FakeUnitOfWork()

    assert hasattr(UnitOfWork, "storage_settings")
    assert isinstance(fake.storage_settings, FakeStorageSettingsRepository)
    assert "storage_settings" in SqlUnitOfWork.__annotations__


def test_the_web_port_exposes_the_storage_use_cases() -> None:
    for name in STORAGE_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
