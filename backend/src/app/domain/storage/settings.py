from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.storage.path import StoragePath
    from app.domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class StoredStorageSettings:
    """저장된 파일 저장 위치(단일 행). 최초 설정이면 updated_by는 None."""

    path: StoragePath
    updated_at: datetime
    updated_by: UserId | None
