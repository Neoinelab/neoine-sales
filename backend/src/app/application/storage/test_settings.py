from typing import TYPE_CHECKING

from app.application.storage.probe import ensure_writable
from app.domain.storage.path import StoragePath

if TYPE_CHECKING:
    from app.application.ports.file_storage import FileStorage


class TestStorageSettings:
    """저장 없이 경로 형식과 쓰기만 확인한다(admin 설정 화면)."""

    __test__ = False  # pytest가 테스트 클래스로 수집하지 않게 한다

    def __init__(self, storage: FileStorage) -> None:
        self._storage = storage

    async def execute(self, raw_path: str) -> None:
        await ensure_writable(self._storage, StoragePath.parse(raw_path))
