from typing import TYPE_CHECKING

from app.application.auth.messages import DIRECTORY_FIRST, SETUP_CLOSED
from app.application.storage.probe import ensure_writable
from app.domain.common.errors import InvalidStateError
from app.domain.storage.path import StoragePath

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.file_storage import FileStorage
    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
    from app.domain.storage.settings import StoredStorageSettings


async def _ensure_open(uow: UnitOfWork) -> None:
    if await uow.users.count_active_admins() > 0:
        raise InvalidStateError(SETUP_CLOSED)


class RegisterSetupStorage:
    """최초 설정 2단계: admin이 생기기 전까지 파일 저장 위치를 등록(덮어쓰기)한다.

    판정 순서: 닫힘 -> AD 설정 없음 -> 경로 형식 -> 쓰기 확인.
    앞에서 걸리면 디스크를 건드리지 않는다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, storage: FileStorage) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._storage = storage

    async def execute(self, raw_path: str) -> StoredStorageSettings:
        async with self._uow_factory() as uow:
            await _ensure_open(uow)
            if await uow.directory_settings.get() is None:
                raise InvalidStateError(DIRECTORY_FIRST)
        path = StoragePath.parse(raw_path)
        await ensure_writable(self._storage, path)
        async with self._uow_factory() as uow:
            await uow.users.lock_roster()
            await _ensure_open(uow)
            stored = await uow.storage_settings.save(path, updated_by=None, now=self._clock.now())
            await uow.commit()
        return stored


class TestSetupStorage:
    """최초 설정 2단계의 쓰기 확인. 저장하지 않고 AD 설정 여부도 보지 않는다."""

    __test__ = False  # pytest가 테스트 클래스로 수집하지 않게 한다

    def __init__(self, uow_factory: UnitOfWorkFactory, storage: FileStorage) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def execute(self, raw_path: str) -> None:
        async with self._uow_factory() as uow:
            await _ensure_open(uow)
        await ensure_writable(self._storage, StoragePath.parse(raw_path))
