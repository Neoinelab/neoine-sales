"""VendorRepository Port의 SQLAlchemy 구현.

이름 고유성은 DB 유니크 인덱스가, Deal의 사용 중 삭제 방지는 FK RESTRICT가 보장하고 위반은
도메인 오류로 바꾼다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import collate, func, select

from app.domain.common.errors import AlreadyExistsError
from app.domain.vendor.entities import Vendor
from app.domain.vendor.errors import (
    DuplicateVendorNameError,
    VendorInUseError,
    VendorNotFoundError,
)
from app.domain.vendor.values import VendorId
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.models_catalog import VendorRow
from app.infra.db.models_deal import DealRow

if TYPE_CHECKING:
    from collections.abc import Sequence

# 코드 포인트 순(Fake의 파이썬 비교와 동일), 동률은 id 순
_VENDOR_ORDER = (collate(func.lower(VendorRow.name), "C"), VendorRow.id)


def _vendor_entity(row: VendorRow) -> Vendor:
    return Vendor(
        id=VendorId(row.id), name=row.name, created_at=row.created_at, updated_at=row.updated_at
    )


def _write_errors(vendor: Vendor) -> ConstraintErrors:
    return {
        "uq_vendors_name_lower": lambda: DuplicateVendorNameError(vendor.name),
        "pk_vendors": lambda: AlreadyExistsError("Vendor", vendor.id),
    }


class SqlVendorRepository(SqlRepository[VendorRow]):
    row_type = VendorRow

    async def list(self, *, for_update: bool = False) -> Sequence[Vendor]:
        statement = select(VendorRow).order_by(*_VENDOR_ORDER)
        if for_update:
            statement = statement.with_for_update()
        rows = (
            await self._session.scalars(statement.execution_options(populate_existing=True))
        ).all()
        return [_vendor_entity(row) for row in rows]

    async def get(self, vendor_id: VendorId, *, for_update: bool = False) -> Vendor:
        return _vendor_entity(await self._row(vendor_id, for_update=for_update))

    async def add(self, vendor: Vendor) -> None:
        row = VendorRow(
            id=vendor.id,
            name=vendor.name,
            created_at=vendor.created_at,
            updated_at=vendor.updated_at,
        )
        await self._insert(row, _write_errors(vendor))

    async def update(self, vendor: Vendor) -> None:
        row = await self._row(vendor.id)

        async def work() -> None:
            row.name = vendor.name
            row.updated_at = vendor.updated_at

        await self._atomic(
            _write_errors(vendor), work, not_found=lambda: VendorNotFoundError(vendor.id)
        )

    async def delete(self, vendor_id: VendorId) -> None:
        row = await self._row(vendor_id)
        in_use: ConstraintErrors = {"fk_deals_vendor_id_vendors": lambda: VendorInUseError(1)}
        try:
            await self._remove(row, in_use)
        except VendorInUseError:
            usage = await self._session.scalar(
                select(func.count()).select_from(DealRow).where(DealRow.vendor_id == vendor_id)
            )
            raise VendorInUseError(max(int(usage or 0), 1)) from None

    async def _row(self, vendor_id: int, *, for_update: bool = False) -> VendorRow:
        statement = select(VendorRow).where(VendorRow.id == vendor_id)
        if for_update:
            statement = statement.with_for_update()
        row = (
            await self._session.scalars(statement.execution_options(populate_existing=True))
        ).one_or_none()
        if row is None:
            raise VendorNotFoundError(vendor_id)
        return row
