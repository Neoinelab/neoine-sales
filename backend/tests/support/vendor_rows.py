"""head 스키마(BIGINT id)에 원시 SQL로 vendors·solutions 행을 넣는 도우미.

제약 검증용이라 도메인 검사를 거치지 않는다. Deal 행은 `head_rows.insert_deal`로 만들고
`link_deal`로 Vendor·Solution을 연결한다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import text

from tests.support.ids import new_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INSERT_VENDOR = (
    "insert into vendors (id, name, created_at, updated_at) values (:id, :name, now(), now())"
)
INSERT_SOLUTION = (
    "insert into solutions (id, vendor_id, name, created_at, updated_at)"
    " values (:id, :vendor_id, :name, now(), now())"
)
LINK_DEAL = (
    "update deals set vendor_id = :vendor_id, solution_id = :solution_id where deal_code = :code"
)


async def insert_vendor(session: AsyncSession, name: str = "SAP") -> int:
    new_vendor_id = new_id()
    await session.execute(text(INSERT_VENDOR), {"id": new_vendor_id, "name": name})
    return new_vendor_id


async def insert_solution(session: AsyncSession, vendor_id: int, name: str = "S/4HANA") -> int:
    new_solution_id = new_id()
    await session.execute(
        text(INSERT_SOLUTION), {"id": new_solution_id, "vendor_id": vendor_id, "name": name}
    )
    return new_solution_id


async def link_deal(
    session: AsyncSession, code: str, vendor_id: int | None, solution_id: int | None
) -> None:
    """Deal의 Vendor·Solution 열을 직접 바꾼다(제약이 거절하면 IntegrityError)."""
    await session.execute(
        text(LINK_DEAL), {"code": code, "vendor_id": vendor_id, "solution_id": solution_id}
    )
