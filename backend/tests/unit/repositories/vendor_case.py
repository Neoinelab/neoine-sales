"""VendorRepository 계약 테스트 공용 case(Fake와 SQL 구현 양쪽).

SQL 구현은 같은 DB에 다른 테스트가 만든 Vendor가 있을 수 있으므로, 계약 테스트는 비어 있는
저장소를 가정하지 않는다(자기가 만든 행만 골라 비교한다: `mine`). Deal이 Vendor를 참조하는 계약은
`deal_case.py`의 DealCase(vendors 포함)가 맡는다. SQL 구현 모듈은 사용 시점에 가져온다.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import pytest

from tests.fakes.vendors import FakeVendorRepository
from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Collection

    from sqlalchemy.engine import URL

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


class VendorCase:
    """한 구현(fake 또는 sql)의 Vendor 저장소. Port 계약만 보고 쓴다."""

    def __init__(self, vendors: Any) -> None:  # noqa: ANN401
        self.vendors = vendors

    async def mine(self, ids: Collection[Any]) -> list[Any]:
        """저장소 목록 중 ids에 있는 Vendor만(저장소 순서 유지)."""
        return [v for v in await self.vendors.list() if v.id in ids]


@asynccontextmanager
async def open_vendor_case(
    implementation: str, test_database_url: URL | None
) -> AsyncIterator[VendorCase]:
    if implementation == "fake":
        yield VendorCase(FakeVendorRepository())
        return
    from app.infra.db.vendor_repository import SqlVendorRepository  # noqa: PLC0415

    async with rolled_back_session(test_database_url) as session:  # type: ignore[arg-type]
        yield VendorCase(SqlVendorRepository(session))
