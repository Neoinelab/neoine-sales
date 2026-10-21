"""head 스키마(BIGINT id)의 deal_attachments·storage_settings에 원시 SQL로 행을 넣는 도우미.

제약 검증용이라 도메인 검사를 거치지 않는다. 첨부는 `deal_code`로 Deal을 찾아 `deal_id`를 채운다
(없는 Deal을 가리키려면 `deal_id=`를 덮어쓴다). `storage_key`는 디스크 파일 키라 무작위 값이다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import text

from tests.support.head_rows import deal_id_of
from tests.support.ids import new_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INSERT_ATTACHMENT = (
    "insert into deal_attachments (id, deal_id, file_name, description, mime, size_bytes,"
    " storage_key, uploaded_by_user_id, uploaded_at, created_at, updated_at) values (:id,"
    " :deal_id, :file_name, :description, :mime, :size_bytes, :storage_key, :uploader,"
    " now(), now(), now())"
)
INSERT_STORAGE_SETTINGS = (
    "insert into storage_settings (id, path, updated_at, updated_by_user_id)"
    " values (:id, :path, now(), :updated_by)"
)


async def insert_attachment(
    session: AsyncSession, deal_code: str, uploader: int, **overrides: object
) -> int:
    """첨부 한 행. 새 첨부 id를 돌려준다. overrides는 INSERT 파라미터를 덮어쓴다."""
    params: dict[str, object] = {
        "id": new_id(),
        "file_name": "a.pdf",
        "description": "",
        "mime": "application/pdf",
        "size_bytes": 10,
        "storage_key": uuid4().hex,
        "uploader": uploader,
        **overrides,
    }
    if "deal_id" not in params:
        params["deal_id"] = await deal_id_of(session, deal_code)
    await session.execute(text(INSERT_ATTACHMENT), params)
    return int(str(params["id"]))


async def insert_storage_settings(session: AsyncSession, **overrides: object) -> None:
    """저장 위치 한 행(기본 id=1, 저장자 없음)."""
    params: dict[str, object] = {
        "id": 1,
        "path": "/data/neoine-sales/files",
        "updated_by": None,
        **overrides,
    }
    await session.execute(text(INSERT_STORAGE_SETTINGS), params)
