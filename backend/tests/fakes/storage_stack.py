"""저장 위치 유스케이스 조립 도우미. 단위 테스트와 FakeUseCases가 같은 방식으로 조립한다.

여기서 고정하는 생성자·실행 계약(구현자가 따른다). 모든 실행은 `execute`다.
- RegisterSetupStorage(uow_factory, clock, storage)        app.application.auth.setup_storage
  execute(raw_path: str) -> StoredStorageSettings           (최초 설정 2단계, 세션 없음)
- TestSetupStorage(uow_factory, storage)                    app.application.auth.setup_storage
  execute(raw_path: str) -> None                            (저장 없이 형식·쓰기 확인만)
- GetStorageSettings(uow_factory)                           app.application.storage.get_settings
  execute() -> StoredStorageSettings                        (없으면 NotFoundError)
- UpdateStorageSettings(uow_factory, clock, storage)        app.application.storage.update_settings
  execute(*, actor: Principal, raw_path: str) -> StoredStorageSettings
- TestStorageSettings(storage)                              app.application.storage.test_settings
  execute(raw_path: str) -> None
- ensure_writable(storage, path: StoragePath) -> None       app.application.storage.probe
  (쓰기 확인 실패를 InvalidValueError(PATH_NOT_WRITABLE)로 바꾼다. 원인은 담지 않는다)
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.auth.setup_storage import RegisterSetupStorage
from app.application.auth.setup_storage import TestSetupStorage as ProbeSetupStorage
from app.application.storage.get_settings import GetStorageSettings
from app.application.storage.test_settings import TestStorageSettings as ProbeStorageSettings
from app.application.storage.update_settings import UpdateStorageSettings
from tests.fakes.file_storage import FakeFileStorage

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class StorageStack:
    storage: FakeFileStorage
    register_setup: RegisterSetupStorage
    test_setup: ProbeSetupStorage
    get_settings: GetStorageSettings
    update_settings: UpdateStorageSettings
    test_settings: ProbeStorageSettings


def build_storage_stack(
    uow_factory: UnitOfWorkFactory, clock: Clock, storage: FakeFileStorage | None = None
) -> StorageStack:
    storage = storage or FakeFileStorage()
    return StorageStack(
        storage=storage,
        register_setup=RegisterSetupStorage(uow_factory, clock, storage),
        test_setup=ProbeSetupStorage(uow_factory, storage),
        get_settings=GetStorageSettings(uow_factory),
        update_settings=UpdateStorageSettings(uow_factory, clock, storage),
        test_settings=ProbeStorageSettings(storage),
    )
