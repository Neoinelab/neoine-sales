"""ContactRepository Port의 SQLAlchemy 구현. 비즈니스 판단 없이 변환·질의·제약 변환만 한다."""

from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, Select, String, case, collate, func, literal, select, text
from sqlalchemy.dialects.postgresql import distinct_on

from app.application.ports.pagination import check_page
from app.domain.common.contact import Email, PhoneNumber
from app.domain.common.errors import AlreadyExistsError
from app.domain.contact.entities import Contact
from app.domain.contact.errors import ContactInUseError, ContactNotFoundError
from app.domain.contact.values import ContactDetails, ContactId, ContactKind
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.contact_usage import deal_counts_by_contacts
from app.infra.db.like import keyword_filter
from app.infra.db.models_contact import ContactRow

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from sqlalchemy.orm import InstrumentedAttribute

    from app.application.ports.contact_repository import ContactQuery

_KIND_ORDER = case(
    {kind.value: index for index, kind in enumerate(ContactKind)}, value=ContactRow.kind
)
_IN_USE_CONSTRAINTS = ("fk_deals_customer_id_contacts", "fk_deal_partners_contact_id_contacts")


def _lower(column: InstrumentedAttribute[str]) -> ColumnElement[str]:
    """소문자 + 코드 포인트 순 정렬(Fake의 파이썬 문자열 비교와 같다)."""
    return collate(func.lower(column), "C")


def _same_lower(column: InstrumentedAttribute[str], value: str) -> ColumnElement[bool]:
    """lower(column) = lower(value). 양쪽 모두 DB의 lower()로 맞춘다(파이썬과 로케일 차이 방지)."""
    return func.lower(column) == func.lower(literal(value, String))


def _apply_details(row: ContactRow, details: ContactDetails) -> None:
    row.company = details.company
    row.name = details.name
    row.title = details.title
    row.email = details.email.value if details.email else None
    row.phone = details.phone.value if details.phone else None


def _to_row(contact: Contact) -> ContactRow:
    row = ContactRow(
        id=contact.id,
        kind=contact.kind.value,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )
    _apply_details(row, contact.details)
    return row


def _to_entity(row: ContactRow) -> Contact:
    return Contact(
        id=ContactId(row.id),
        kind=ContactKind(row.kind),
        details=ContactDetails(
            company=row.company,
            name=row.name,
            title=row.title,
            email=Email(row.email) if row.email else None,
            phone=PhoneNumber(row.phone) if row.phone else None,
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _filtered(query: ContactQuery) -> Select[ContactRow]:
    statement = select(ContactRow)
    if query.kind is not None:
        statement = statement.where(ContactRow.kind == query.kind.value)
    if query.keyword is not None:
        statement = statement.where(
            keyword_filter(query.keyword, ContactRow.company, ContactRow.name, ContactRow.email)
        )
    return statement


class SqlContactRepository(SqlRepository[ContactRow]):
    row_type = ContactRow

    async def add(self, contact: Contact) -> None:
        await self._insert(
            _to_row(contact), {"pk_contacts": lambda: AlreadyExistsError("연락처", contact.id)}
        )

    async def get(self, contact_id: ContactId, *, for_update: bool = False) -> Contact:
        if for_update:
            # FOR NO KEY UPDATE: 같은 연락처를 참조하는 Deal 등록(FK의 KEY SHARE)은 막지 않는다.
            # 삭제 자체가 행을 지울 때 FK(RESTRICT)가 마지막으로 막는다.
            locked = (
                select(ContactRow)
                .where(ContactRow.id == contact_id)
                .with_for_update(key_share=True)
            )
            row = (
                await self._session.scalars(locked.execution_options(populate_existing=True))
            ).one_or_none()
        else:
            row = await self._find(contact_id)
        if row is None:
            raise ContactNotFoundError(contact_id)
        return _to_entity(row)

    async def get_many(self, contact_ids: Collection[ContactId]) -> Mapping[ContactId, Contact]:
        """id별 연락처. 없는 id는 빠지고 중복은 한 번만 읽는다(질의 1회)."""
        wanted = set(contact_ids)
        if not wanted:
            return {}
        statement = (
            select(ContactRow)
            .where(ContactRow.id.in_(wanted))
            .execution_options(populate_existing=True)
        )
        rows = (await self._session.scalars(statement)).all()
        return {ContactId(row.id): _to_entity(row) for row in rows}

    async def search(self, query: ContactQuery) -> Sequence[Contact]:
        check_page(query.offset, query.limit)
        statement = (
            _filtered(query)
            .order_by(
                _KIND_ORDER, _lower(ContactRow.company), _lower(ContactRow.name), ContactRow.id
            )
            .offset(query.offset)
            .limit(query.limit)
            .execution_options(populate_existing=True)
        )
        return [_to_entity(row) for row in (await self._session.scalars(statement)).all()]

    async def count(self, query: ContactQuery) -> int:
        statement = select(func.count()).select_from(_filtered(query).subquery())
        return int(await self._session.scalar(statement) or 0)

    async def companies(self, kind: ContactKind) -> Sequence[str]:
        """kind 안의 회사명. lower(company)가 같으면 가장 먼저 등록된 표기를 대표로 쓴다."""
        lowered = func.lower(ContactRow.company)
        representative = (
            select(ContactRow.company.label("company"), lowered.label("lowered"))
            .where(ContactRow.kind == kind.value)
            .ext(distinct_on(lowered))
            .order_by(lowered, ContactRow.created_at, ContactRow.id)
            .subquery()
        )
        statement = select(representative.c.company).order_by(
            collate(representative.c.lowered, "C")
        )
        return list((await self._session.scalars(statement)).all())

    async def of_company(self, kind: ContactKind, company: str) -> Sequence[Contact]:
        statement = (
            select(ContactRow)
            .where(ContactRow.kind == kind.value, _same_lower(ContactRow.company, company))
            .order_by(_lower(ContactRow.name), ContactRow.id)
            .execution_options(populate_existing=True)
        )
        return [_to_entity(row) for row in (await self._session.scalars(statement)).all()]

    async def same_identity(self, kind: ContactKind, company: str, name: str) -> Sequence[Contact]:
        statement = (
            select(ContactRow)
            .where(
                ContactRow.kind == kind.value,
                _same_lower(ContactRow.company, company),
                _same_lower(ContactRow.name, name),
            )
            .order_by(ContactRow.id)
            .execution_options(populate_existing=True)
        )
        return [_to_entity(row) for row in (await self._session.scalars(statement)).all()]

    async def lock_identity(self, kind: ContactKind, company: str, name: str) -> None:
        """(kind, lower(company), lower(name)) 단위 트랜잭션 advisory lock. 커밋·롤백 때 풀린다."""
        await self._session.execute(
            text(
                "select pg_advisory_xact_lock(hashtextextended("
                "'contact:' || cast(:kind as text) || ':' || lower(cast(:company as text))"
                " || ':' || lower(cast(:name as text)), 0))"
            ),
            {"kind": kind.value, "company": company, "name": name},
        )

    async def update(self, contact: Contact) -> None:
        row = await self._find(contact.id)
        if row is None:
            raise ContactNotFoundError(contact.id)
        _apply_details(row, contact.details)
        row.updated_at = contact.updated_at
        await self._save({}, not_found=lambda: ContactNotFoundError(contact.id))

    async def delete(self, contact_id: ContactId) -> None:
        """물리 삭제. 참조하는 Deal이 FK(RESTRICT)로 막으면 ContactInUseError."""
        row = await self._find(contact_id)
        if row is None:
            raise ContactNotFoundError(contact_id)
        in_use: ConstraintErrors = {
            name: lambda: ContactInUseError(1) for name in _IN_USE_CONSTRAINTS
        }
        try:
            await self._remove(row, in_use)
        except ContactInUseError:
            raise ContactInUseError(max(await self._referencing_deals(contact_id), 1)) from None

    async def _referencing_deals(self, contact_id: ContactId) -> int:
        counts = await deal_counts_by_contacts(self._session, [contact_id])
        return counts[contact_id]
