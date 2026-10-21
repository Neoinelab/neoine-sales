"""head 스키마(P2b)의 deal_attachments·storage_settings에 원시 SQL로 행을 넣는 도우미.

제약 검증용이라 도메인 검사를 거치지 않는다.
"""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INSERT_ATTACHMENT = (
    "insert into deal_attachments (id, deal_code, file_name, description, mime, size_bytes,"
    " storage_key, uploaded_by_user_id, uploaded_at, created_at, updated_at) values (:id,"
    " :deal_code, :file_name, :description, :mime, :size_bytes, :storage_key, :uploader,"
    " now(), now(), now())"
)
INSERT_STORAGE_SETTINGS = (
    "insert into storage_settings (id, path, updated_at, updated_by_user_id)"
    " values (:id, :path, now(), :updated_by)"
)


async def insert_attachment(
    session: AsyncSession, deal_code: str, uploader: UUID, **overrides: object
) -> UUID:
    """첨부 한 행. 새 첨부 id를 돌려준다. overrides는 INSERT 파라미터를 덮어쓴다."""
    params: dict[str, object] = {
        "id": uuid4(),
        "deal_code": deal_code,
        "file_name": "a.pdf",
        "description": "",
        "mime": "application/pdf",
        "size_bytes": 10,
        "storage_key": uuid4().hex,
        "uploader": uploader,
        **overrides,
    }
    await session.execute(text(INSERT_ATTACHMENT), params)
    return UUID(str(params["id"]))


async def insert_storage_settings(session: AsyncSession, **overrides: object) -> None:
    """저장 위치 한 행(기본 id=1, 저장자 없음)."""
    params: dict[str, object] = {
        "id": 1,
        "path": "/data/neoine-sales/files",
        "updated_by": None,
        **overrides,
    }
    await session.execute(text(INSERT_STORAGE_SETTINGS), params)
