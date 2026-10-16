"""DealRepository Port의 SQLAlchemy 구현. 키는 Deal code이고 삭제는 물리 삭제(딸린 데이터 CASCADE).

Deal 행과 파트너 링크·BANT 선택은 한 SAVEPOINT 안에서 함께 저장한다. 중복 code·참조 위반은
도메인 오류로 바꾸되 업무 규칙은 판단하지 않는다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import exists, func, select, update

from app.application.ports.deal_repository import (
    ContactReference,
    DealListItem,
    NextActionSummary,
)
from app.domain.common.errors import InvalidReferenceError
from app.domain.contact.values import ContactKind
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError, DuplicateDealCodeError
from app.infra.db import deal_aggregates, deal_children, deal_mapping, deal_search
from app.infra.db.base_repository import ConstraintErrors, SavepointWriter
from app.infra.db.contact_usage import deal_counts_by_contacts
from app.infra.db.models_deal import DealPartnerRow, DealRow

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence
    from datetime import datetime

    from app.application.ports.deal_repository import DealDeletionImpact, DealQuery
    from app.domain.bant.values import BantLabelId
    from app.domain.contact.values import ContactId
    from app.domain.deal.entities import Deal
    from app.infra.db.deal_search import ItemSelect


def _write_errors(deal: Deal) -> ConstraintErrors:
    """INSERT·UPDATE 제약 위반의 도메인 오류. 참조 FK는 삭제와의 경쟁에서도 발생한다."""
    details = deal.details
    return {
        "pk_deals": lambda: DuplicateDealCodeError(deal.id.value),
        "fk_deals_customer_id_contacts": lambda: InvalidReferenceError(
            "고객 연락처", deal.customer_id
        ),
        "fk_deal_partners_contact_id_contacts": lambda: InvalidReferenceError(
            "파트너 연락처", deal.active_partner_id()
        ),
        "fk_deals_owner_user_id_users": lambda: InvalidReferenceError(
            "사용자", details.owner_user_id
        ),
        "fk_deals_status_code": lambda: InvalidReferenceError("Status 코드", deal.sync.status_key),
        "fk_deals_forecast_code": lambda: InvalidReferenceError(
            "Forecast 코드", deal.sync.forecast_key
        ),
        "fk_deal_bant_labels_label": lambda: InvalidReferenceError("BANT Label", "선택한 Label"),
    }


class SqlDealRepository(SavepointWriter):
    # --- 쓰기 ---

    async def add(self, deal: Deal) -> None:
        async def work() -> None:
            self._session.add(deal_mapping.new_row(deal))
            await self._session.flush()  # 자식 행이 참조할 deals 행을 먼저 보낸다
            self._session.add_all(
                deal_children.partner_row(deal.id.value, link) for link in deal.partner_links
            )
            self._session.add_all(deal_children.bant_rows(deal, {}))

        await self._atomic(_write_errors(deal), work)

    async def update(self, deal: Deal) -> None:
        row = await self._session.get(DealRow, deal.id.value, populate_existing=True)
        if row is None:
            raise DealNotFoundError(deal.id.value)

        async def work() -> None:
            deal_mapping.apply_fields(row, deal)
            await self._session.flush()
            await deal_children.sync_partners(self._session, deal)
            await deal_children.sync_bant(self._session, deal)

        await self._atomic(
            _write_errors(deal), work, not_found=lambda: DealNotFoundError(deal.id.value)
        )

    async def touch(self, codes: Collection[DealCode], now: datetime) -> None:
        values = [code.value for code in codes]
        if not values:
            return
        statement = (
            update(DealRow)
            .where(DealRow.deal_code.in_(values))
            .values(updated_at=now)
            .execution_options(synchronize_session=False)
        )
        await self._session.execute(statement)

    async def delete(self, code: DealCode) -> None:
        row = await self._session.get(DealRow, code.value, populate_existing=True)
        if row is None:
            raise DealNotFoundError(code.value)
        await self._remove(row, {})

    # --- 읽기 ---

    async def get(self, code: DealCode, *, for_update: bool = False) -> Deal:
        statement = select(DealRow).where(DealRow.deal_code == code.value)
        if for_update:
            statement = statement.with_for_update()
        row = (
            await self._session.scalars(statement.execution_options(populate_existing=True))
        ).one_or_none()
        if row is None:
            raise DealNotFoundError(code.value)
        return (await deal_children.hydrate(self._session, [row]))[0]

    async def exists(self, code: DealCode) -> bool:
        return bool(
            await self._session.scalar(select(exists().where(DealRow.deal_code == code.value)))
        )

    async def _items(self, statement: ItemSelect) -> list[DealListItem]:
        result = await self._session.execute(statement.execution_options(populate_existing=True))
        rows = result.all()
        deals = await deal_children.hydrate(self._session, [row.DealRow for row in rows])
        return [
            DealListItem(
                deal=deal,
                next_action=(
                    None
                    if row.next_action is None
                    else NextActionSummary(row.next_action, row.due_date)
                ),
                last_updated_at=row.last_updated_at,
            )
            for row, deal in zip(rows, deals, strict=True)
        ]

    async def get_item(self, code: DealCode) -> DealListItem:
        items = await self._items(deal_search.item_select().where(DealRow.deal_code == code.value))
        if not items:
            raise DealNotFoundError(code.value)
        return items[0]

    async def search(self, query: DealQuery) -> Sequence[DealListItem]:
        return await self._items(deal_search.search_select(query))

    async def count(self, query: DealQuery) -> int:
        statement = select(func.count()).select_from(DealRow).where(*deal_search.conditions(query))
        return int(await self._session.scalar(statement) or 0)

    async def references_of_contact(self, contact_id: ContactId) -> Sequence[ContactReference]:
        """고객으로 참조하는 Deal, 파트너 링크(비활성 포함)로 참조하는 Deal. 각각 code 순서."""
        customers = select(DealRow.deal_code).where(DealRow.customer_id == contact_id)
        partners = select(DealPartnerRow.deal_code).where(DealPartnerRow.contact_id == contact_id)
        found: list[ContactReference] = []
        for kind, statement in ((ContactKind.CUSTOMER, customers), (ContactKind.PARTNER, partners)):
            ordered = statement.order_by(statement.selected_columns.deal_code)
            codes = (await self._session.scalars(ordered)).all()
            found.extend(ContactReference(DealCode(code), kind) for code in codes)
        return found

    # --- 집계 ---

    async def facets(self) -> tuple[Sequence[str], Sequence[str]]:
        return await deal_aggregates.facets(self._session)

    async def deletion_impact(self, code: DealCode) -> DealDeletionImpact:
        if not await self.exists(code):
            raise DealNotFoundError(code.value)
        return await deal_aggregates.deletion_impact(self._session, code.value)

    async def count_by_status(self) -> Mapping[str, int]:
        return await deal_aggregates.count_by_status(self._session)

    async def count_by_forecast(self) -> Mapping[str, int]:
        return await deal_aggregates.count_by_forecast(self._session)

    async def count_by_bant_label(self) -> Mapping[BantLabelId, int]:
        return await deal_aggregates.count_by_bant_label(self._session)

    async def count_by_contacts(self, contact_ids: Sequence[ContactId]) -> Mapping[ContactId, int]:
        """연락처별 참조 Deal 수. 요청한 id는 모두 키로 두고, 한 Deal은 연락처당 1건이다."""
        return await deal_counts_by_contacts(self._session, contact_ids)
