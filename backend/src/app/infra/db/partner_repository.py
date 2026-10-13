"""PartnerRepository Port의 SQLAlchemy 구현."""

from typing import TYPE_CHECKING

from app.application.ports.pagination import DEFAULT_LIMIT
from app.domain.common.contact import Email, PhoneNumber
from app.domain.common.errors import AlreadyExistsError
from app.domain.partner.entities import Partner
from app.domain.partner.errors import PartnerInUseError, PartnerNotFoundError
from app.domain.partner.value_objects import PartnerDetails, PartnerId
from app.infra.db.base_repository import SqlRepository
from app.infra.db.like import keyword_filter
from app.infra.db.models import PartnerRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.partner_repository import PartnerQuery


def _apply_details(row: PartnerRow, details: PartnerDetails) -> None:
    row.company_name = details.company_name
    row.contact_name = details.contact_name
    row.contact_title = details.contact_title
    row.email = details.email.value if details.email else None
    row.phone = details.phone.value if details.phone else None


def _to_row(partner: Partner) -> PartnerRow:
    row = PartnerRow(
        id=partner.id,
        created_at=partner.created_at,
        updated_at=partner.updated_at,
    )
    _apply_details(row, partner.details)
    return row


def _to_entity(row: PartnerRow) -> Partner:
    return Partner(
        id=PartnerId(row.id),
        details=PartnerDetails(
            company_name=row.company_name,
            contact_name=row.contact_name,
            contact_title=row.contact_title,
            email=Email(row.email) if row.email else None,
            phone=PhoneNumber(row.phone) if row.phone else None,
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlPartnerRepository(SqlRepository[PartnerRow]):
    row_type = PartnerRow

    async def add(self, partner: Partner) -> None:
        await self._insert(
            _to_row(partner), {"pk_partners": lambda: AlreadyExistsError("파트너", partner.id)}
        )

    async def get(self, partner_id: PartnerId) -> Partner:
        row = await self._find(partner_id)
        if row is None:
            raise PartnerNotFoundError(partner_id)
        return _to_entity(row)

    async def list(self, *, offset: int = 0, limit: int = DEFAULT_LIMIT) -> Sequence[Partner]:
        rows = await self._page(offset, limit)
        return [_to_entity(row) for row in rows]

    async def search(self, query: PartnerQuery) -> Sequence[Partner]:
        condition = (
            None
            if query.keyword is None
            else keyword_filter(
                query.keyword,
                PartnerRow.company_name,
                PartnerRow.contact_name,
                PartnerRow.contact_title,
                PartnerRow.email,
                PartnerRow.phone,
            )
        )
        rows = await self._page(query.offset, query.limit, condition=condition)
        return [_to_entity(row) for row in rows]

    async def update(self, partner: Partner) -> None:
        row = await self._find(partner.id)
        if row is None:
            raise PartnerNotFoundError(partner.id)
        _apply_details(row, partner.details)
        row.updated_at = partner.updated_at
        await self._save({})

    async def delete(self, partner_id: PartnerId) -> None:
        """물리 삭제. 참조하는 Deal이 FK(RESTRICT)로 막으면 PartnerInUseError."""
        row = await self._find(partner_id)
        if row is None:
            raise PartnerNotFoundError(partner_id)
        await self._remove(
            row, {"fk_deals_partner_id_partners": lambda: PartnerInUseError(partner_id)}
        )
