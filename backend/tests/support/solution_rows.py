"""Solution 텍스트 리비전 *직전* 스키마(`solutions` 테이블, `deals.solution_id`)용 원시 SQL 도우미.

마이그레이션 시나리오가 "목록에서 고른 Solution이 있는 Deal"을 운영 중 데이터로 만들 때 쓴다.
head 스키마에는 `solutions`가 없으므로 head를 대상으로 쓰면 안 된다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import text

from tests.support.ids import new_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INSERT_SOLUTION = (
    "insert into solutions (id, vendor_id, name, created_at, updated_at)"
    " values (:id, :vendor_id, :name, now(), now())"
)
LINK_DEAL = (
    "update deals set vendor_id = :vendor_id, solution_id = :solution_id where deal_code = :code"
)


async def insert_solution(session: AsyncSession, vendor_id: int, name: str = "S/4HANA") -> int:
    """Vendor 소속 Solution 한 행을 넣고 id를 돌려준다."""
    solution_id = new_id()
    await session.execute(
        text(INSERT_SOLUTION), {"id": solution_id, "vendor_id": vendor_id, "name": name}
    )
    return solution_id


async def link_deal(
    session: AsyncSession, code: str, vendor_id: int | None, solution_id: int | None
) -> None:
    """Deal의 Vendor·Solution id 열을 직접 바꾼다(복합 FK·CHECK가 거절하면 IntegrityError)."""
    await session.execute(
        text(LINK_DEAL), {"code": code, "vendor_id": vendor_id, "solution_id": solution_id}
    )
