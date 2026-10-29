"""DirectorySettingsRepository Port의 InMemory 구현(Fake). 단일 행(id=1)과 revision 낙관적 잠금."""

from typing import TYPE_CHECKING

from app.domain.directory.errors import DirectorySettingsConflictError
from app.domain.directory.settings import StoredDirectorySettings

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.common.secret import SealedSecret

    from app.domain.directory.settings import DirectoryConnection
    from app.domain.user.value_objects import UserId

_ROW = 1


class FakeDirectorySettingsRepository:
    def __init__(self) -> None:
        self._items: dict[int, StoredDirectorySettings] = {}

    async def get(self) -> StoredDirectorySettings | None:
        return self._items.get(_ROW)

    async def save(  # noqa: PLR0913 - Port 시그니처와 같다
        self,
        connection: DirectoryConnection,
        sealed_bind_password: SealedSecret,
        base_dn: str,
        *,
        expected_revision: int | None,
        updated_by: UserId | None,
        now: datetime,
    ) -> StoredDirectorySettings:
        current = self._items.get(_ROW)
        if expected_revision is None:
            if current is not None:
                raise DirectorySettingsConflictError
            revision = 1
        else:
            if current is None or current.revision != expected_revision:
                raise DirectorySettingsConflictError
            revision = expected_revision + 1
        stored = StoredDirectorySettings(
            connection=connection,
            sealed_bind_password=sealed_bind_password,
            base_dn=base_dn,
            revision=revision,
            updated_at=now,
            updated_by=updated_by,
        )
        self._items[_ROW] = stored  # 값 객체(frozen)라 복사가 필요 없다
        return stored
