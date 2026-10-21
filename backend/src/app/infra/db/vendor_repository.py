"""VendorRepository Port의 SQLAlchemy 구현. Vendor와 소속 Solution을 한 Aggregate로 저장한다.

이름 고유성은 DB 유니크 인덱스가, Deal의 사용 중 삭제 방지는 FK RESTRICT가 보장하고 위반은
도메인 오류로 바꾼다. Solution 목록 동기화는 한 SAVEPOINT 안에서 삭제, 이름 변경, 추가 순으로 쓴다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import collate, func, select

from app.domain.common.errors import AlreadyExistsError
from app.domain.vendor.entities import Solution, Vendor
from app.domain.vendor.errors import (
    DuplicateSolutionNameError,
    DuplicateVendorNameError,
    SolutionInUseError,
    VendorInUseError,
    VendorNotFoundError,
)
from app.domain.vendor.values import SolutionId, VendorId
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.models_catalog import SolutionRow, VendorRow
from app.infra.db.models_deal import DealRow

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

type _SolutionRows = list[SolutionRow]

# 코드 포인트 순(Fake의 파이썬 비교와 동일), 동률은 id 순
_VENDOR_ORDER = (collate(func.lower(VendorRow.name), "C"), VendorRow.id)
_SOLUTION_ORDER = (collate(func.lower(SolutionRow.name), "C"), SolutionRow.id)


def _solution_entity(row: SolutionRow) -> Solution:
    return Solution(
        id=SolutionId(row.id), name=row.name, created_at=row.created_at, updated_at=row.updated_at
    )


def _vendor_entity(row: VendorRow, solutions: Sequence[SolutionRow]) -> Vendor:
    return Vendor(
        id=VendorId(row.id),
        name=row.name,
        solutions=[_solution_entity(s) for s in solutions],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _duplicate_solution_name(vendor: Vendor) -> str:
    """대소문자를 무시하고 겹치는 Solution 이름(나중에 나온 쪽)을 돌려준다."""
    seen: set[str] = set()
    for solution in vendor.solutions:
        if solution.name.lower() in seen:
            return solution.name
        seen.add(solution.name.lower())
    return vendor.solutions[-1].name if vendor.solutions else vendor.name


def _write_errors(vendor: Vendor) -> ConstraintErrors:
    return {
        "uq_vendors_name_lower": lambda: DuplicateVendorNameError(vendor.name),
        "uq_solutions_vendor_id_name_lower": lambda: DuplicateSolutionNameError(
            _duplicate_solution_name(vendor)
        ),
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
        solutions = await self._solutions([row.id for row in rows])
        return [_vendor_entity(row, solutions.get(row.id, [])) for row in rows]

    async def get(self, vendor_id: VendorId, *, for_update: bool = False) -> Vendor:
        row = await self._row(vendor_id, for_update=for_update)
        solutions = await self._solutions([row.id])
        return _vendor_entity(row, solutions.get(row.id, []))

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
        current = {s.id: s for s in (await self._solutions([row.id])).get(row.id, [])}
        wanted = {s.id: s for s in vendor.solutions}
        removed = [current[key] for key in current if key not in wanted]

        async def work() -> None:
            row.name = vendor.name
            row.updated_at = vendor.updated_at
            for gone in removed:
                await self._session.delete(gone)
            await self._session.flush()  # 이름 교환에 앞서 삭제할 이름을 비운다
            for solution in vendor.solutions:
                if solution.id in current:
                    found = current[solution.id]
                    found.name = solution.name
                    found.updated_at = solution.updated_at
            await self._session.flush()
            self._session.add_all(
                SolutionRow(
                    id=s.id,
                    vendor_id=vendor.id,
                    name=s.name,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                )
                for s in vendor.solutions
                if s.id not in current
            )

        errors: ConstraintErrors = {
            **_write_errors(vendor),
            "fk_deals_solution": lambda: SolutionInUseError(1),
        }
        try:
            await self._atomic(errors, work, not_found=lambda: VendorNotFoundError(vendor.id))
        except SolutionInUseError:
            raise SolutionInUseError(
                max(await self._solution_usage([s.id for s in removed]), 1)
            ) from None

    async def delete(self, vendor_id: VendorId) -> None:
        row = await self._row(vendor_id)
        in_use: ConstraintErrors = {
            "fk_deals_vendor_id_vendors": lambda: VendorInUseError(1),
            "fk_deals_solution": lambda: VendorInUseError(1),
        }
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

    async def _solutions(self, vendor_ids: Collection[int]) -> dict[int, _SolutionRows]:
        grouped: dict[int, _SolutionRows] = {}
        if not vendor_ids:
            return grouped
        statement = (
            select(SolutionRow)
            .where(SolutionRow.vendor_id.in_(vendor_ids))
            .order_by(*_SOLUTION_ORDER)
            .execution_options(populate_existing=True)
        )
        for solution in (await self._session.scalars(statement)).all():
            grouped.setdefault(solution.vendor_id, []).append(solution)
        return grouped

    async def _solution_usage(self, solution_ids: Collection[int]) -> int:
        statement = (
            select(func.count()).select_from(DealRow).where(DealRow.solution_id.in_(solution_ids))
        )
        return int(await self._session.scalar(statement) or 0)
