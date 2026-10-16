"""파일 저장 위치 스키마(P2b). 경로 형식·길이 판단은 도메인이 하고 스키마는 모양만 본다."""

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.web.schemas.common import RequestModel
from app.web.schemas.user_ref import UserRef, ref_of, resolve_refs

if TYPE_CHECKING:
    from app.domain.storage.settings import StoredStorageSettings
    from app.web.use_case_provider import UseCaseProvider


class StorageSettingsRequest(RequestModel):
    path: str


class StorageSettingsResponse(BaseModel):
    path: str
    updated_at: datetime
    updated_by: UserRef | None


async def storage_response(
    provider: UseCaseProvider, stored: StoredStorageSettings
) -> StorageSettingsResponse:
    """저장자(updated_by) 표시 이름을 풀어 응답으로 만든다. 최초 설정이면 None."""
    refs = await resolve_refs(provider, [stored.updated_by])
    updated_by = None if stored.updated_by is None else ref_of(refs, stored.updated_by)
    return StorageSettingsResponse(
        path=stored.path.value, updated_at=stored.updated_at, updated_by=updated_by
    )
