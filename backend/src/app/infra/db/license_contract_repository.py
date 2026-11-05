"""LicenseContractRepository Port의 SQLAlchemy 구현.

발급 상태 유일성은 부분 유니크 인덱스가 보장하고, 위반은 SAVEPOINT 안에서
LicenseAlreadyIssuedError로 바뀐다. 여기서는 업무 규칙을 판단하지 않는다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select

from app.domain.deal.errors import DealNotFoundError
from app.domain.license_contract.errors import LicenseContractNotFoundError
from app.domain.license_contract.values import LicenseContractId
from app.infra.db import license_contract_mapping as mapping
from app.infra.db import license_contract_query as query_sql
from app.infra.db.base_repository import SqlRepository
from app.infra.db.deal_keys import deal_id_of
from app.infra.db.models_deal import DealRow
from app.infra.db.models_license_contract import ISSUED_STATUSES, LicenseContractRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.license_contract_repository import (
        LicenseContractQuery,
    )
    from app.application.ports.license_contract_repository import (
        LicenseContractRow as ContractRowView,
    )
    from app.domain.deal.code import DealCode
    from app.domain.license_contract.entities import LicenseContract


class SqlLicenseContractRepository(SqlRepository[LicenseContractRow]):
    row_type = LicenseContractRow

    async def add(self, contract: LicenseContract) -> None:
        code = contract.deal_code.value
        deal_id = await deal_id_of(self._session, code)
        if deal_id is None:
            raise DealNotFoundError(code)
        await self._insert(mapping.new_row(contract, deal_id), mapping.write_errors(contract))

    async def get(
        self, contract_id: LicenseContractId, *, for_update: bool = False
    ) -> LicenseContract:
        statement = (
            select(LicenseContractRow, DealRow.deal_code)
            .join(DealRow, DealRow.id == LicenseContractRow.deal_id)
            .where(LicenseContractRow.id == contract_id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update(of=LicenseContractRow)
        found = (await self._session.execute(statement)).one_or_none()
        if found is None:
            raise LicenseContractNotFoundError(contract_id)
        return mapping.to_entity(*found)

    async def get_row(self, contract_id: LicenseContractId) -> ContractRowView:
        statement = query_sql.row_select().where(LicenseContractRow.id == contract_id)
        found = (await self._session.execute(statement)).one_or_none()
        if found is None:
            raise LicenseContractNotFoundError(contract_id)
        return mapping.to_view(found)

    async def update(self, contract: LicenseContract) -> None:
        row = await self._find(contract.id)
        if row is None:
            raise LicenseContractNotFoundError(contract.id)
        mapping.apply_changes(row, contract)
        await self._save(
            mapping.write_errors(contract),
            not_found=lambda: LicenseContractNotFoundError(contract.id),
        )

    async def delete(self, contract_id: LicenseContractId) -> None:
        row = await self._find(contract_id)
        if row is None:
            raise LicenseContractNotFoundError(contract_id)
        await self._remove(row, {})

    async def count_of_deal(self, deal_code: DealCode) -> int:
        statement = (
            select(func.count(LicenseContractRow.id))
            .join(DealRow, DealRow.id == LicenseContractRow.deal_id)
            .where(DealRow.deal_code == deal_code.value)
        )
        return int(await self._session.scalar(statement) or 0)

    async def ids_of_deal(self, deal_code: DealCode) -> Sequence[LicenseContractId]:
        statement = (
            select(LicenseContractRow.id)
            .join(DealRow, DealRow.id == LicenseContractRow.deal_id)
            .where(DealRow.deal_code == deal_code.value)
            .order_by(LicenseContractRow.id)
        )
        return [
            LicenseContractId(found) for found in (await self._session.scalars(statement)).all()
        ]

    async def delete_of_deal(self, deal_code: DealCode) -> int:
        deal_ids = select(DealRow.id).where(DealRow.deal_code == deal_code.value)
        statement = (
            delete(LicenseContractRow)
            .where(LicenseContractRow.deal_id.in_(deal_ids))
            .execution_options(synchronize_session=False)
        )
        result = await self._session.execute(statement)
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def issued_of_deal(self, deal_code: DealCode) -> LicenseContract | None:
        statement = (
            select(LicenseContractRow)
            .join(DealRow, DealRow.id == LicenseContractRow.deal_id)
            .where(
                DealRow.deal_code == deal_code.value,
                LicenseContractRow.status.in_(ISSUED_STATUSES),
            )
            .execution_options(populate_existing=True)
        )
        row = (await self._session.scalars(statement)).first()
        return None if row is None else mapping.to_entity(row, deal_code.value)

    async def search(self, query: LicenseContractQuery) -> Sequence[ContractRowView]:
        found = (await self._session.execute(query_sql.search_select(query))).all()
        return [mapping.to_view(row) for row in found]

    async def count(self, query: LicenseContractQuery) -> int:
        return int(await self._session.scalar(query_sql.count_select(query)) or 0)
