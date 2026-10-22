"""head 스키마(BIGINT id)에 원시 SQL로 vendors 행을 넣는 도우미.

제약 검증용이라 도메인 검사를 거치지 않는다. Deal 행은 `head_rows.insert_deal`로 만들고
`link_deal`로 Vendor를 연결하고 Solution 텍스트를 넣는다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import text

from tests.support.ids import new_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INSERT_VENDOR = (
    "insert into vendors (id, name, created_at, updated_at) values (:id, :name, now(), now())"
)
LINK_DEAL = "update deals set vendor_id = :vendor_id, solution = :solution where deal_code = :code"


async def insert_vendor(session: AsyncSession, name: str = "SAP") -> int:
    new_vendor_id = new_id()
    await session.execute(text(INSERT_VENDOR), {"id": new_vendor_id, "name": name})
    return new_vendor_id


async def link_deal(
    session: AsyncSession, code: str, vendor_id: int | None, solution: str = ""
) -> None:
    """Deal의 Vendor 열과 Solution 텍스트 열을 직접 바꾼다(제약이 거절하면 IntegrityError)."""
    await session.execute(
        text(LINK_DEAL), {"code": code, "vendor_id": vendor_id, "solution": solution}
    )
