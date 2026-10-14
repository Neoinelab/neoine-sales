from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.directory.settings import DirectorySettings, StoredDirectorySettings
    from app.domain.user.value_objects import UserId


class DirectorySettingsRepository(Protocol):
    async def get(self) -> StoredDirectorySettings | None: ...

    async def save(
        self,
        settings: DirectorySettings,
        *,
        expected_revision: int | None,
        updated_by: UserId | None,
        now: datetime,
    ) -> StoredDirectorySettings:
        """낙관적 잠금 저장.

        expected_revision=None이면 행이 없을 때만 만든다(revision 1). 이미 있으면
        DirectorySettingsConflictError. 정수이면 그 revision일 때만 갱신(revision+1)하고,
        다르면 DirectorySettingsConflictError.
        """
        ...
