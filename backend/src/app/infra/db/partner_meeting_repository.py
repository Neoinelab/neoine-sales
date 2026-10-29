"""PartnerMeetingRepository Port의 SQLAlchemy 구현. Deal·작성자 존재는 DB 제약이 보장한다."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import aliased

from app.application.ports.deal_repository import SortOrder
from app.application.ports.partner_meeting_repository import (
    PartnerDealChoice,
    PartnerMeetingRecord,
    PartnerMeetingSort,
)
from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.contact.values import ContactKind
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.partner_meeting.entities import PartnerMeeting
from app.domain.partner_meeting.errors import PartnerMeetingNotFoundError
from app.domain.partner_meeting.values import MeetingContent, MeetingSubject, PartnerMeetingId
from app.domain.user.value_objects import UserId
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.deal_keys import deal_id_of
from app.infra.db.like import LIKE_ESCAPE, like_pattern
from app.infra.db.models_auth import UserRow
from app.infra.db.models_contact import ContactRow
from app.infra.db.models_deal import DealPartnerRow, DealRow
from app.infra.db.models_meeting import PartnerMeetingRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.orm import InstrumentedAttribute

    from app.application.ports.partner_meeting_repository import PartnerMeetingQuery
    from app.domain.common.errors import DomainError


def _to_entity(row: PartnerMeetingRow, deal_code: str) -> PartnerMeeting:
    return PartnerMeeting(
        id=PartnerMeetingId(row.id),
        subject=MeetingSubject(row.partner_company, DealCode(deal_code)),
        meeting_date=row.meeting_date,
        content=MeetingContent(row.content),
        author_user_id=UserId(row.created_by_user_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _apply_content(row: PartnerMeetingRow, meeting: PartnerMeeting, deal_id: int) -> None:
    row.deal_id = deal_id
    row.partner_company = meeting.subject.partner_company
    row.meeting_date = meeting.meeting_date
    row.content = meeting.content.value
    row.updated_at = meeting.updated_at


def _write_errors(meeting: PartnerMeeting) -> ConstraintErrors:
    def deal_missing() -> DomainError:
        return DealNotFoundError(meeting.subject.deal_code.value)

    return {
        "fk_partner_meetings_deal_id_deals": deal_missing,
        "fk_partner_meetings_created_by_user_id_users": lambda: InvalidReferenceError(
            "사용자", meeting.author_user_id
        ),
        "pk_partner_meetings": lambda: AlreadyExistsError("미팅 기록", meeting.id),
    }


def _contains(
    column: ColumnElement[str] | InstrumentedAttribute[str], keyword: str
) -> ColumnElement[bool]:
    return column.ilike(like_pattern(keyword), escape=LIKE_ESCAPE)


class SqlPartnerMeetingRepository(SqlRepository[PartnerMeetingRow]):
    row_type = PartnerMeetingRow

    async def add(self, meeting: PartnerMeeting) -> None:
        code = meeting.subject.deal_code.value
        deal_id = await deal_id_of(self._session, code)
        if deal_id is None:
            raise DealNotFoundError(code)
        row = PartnerMeetingRow(id=meeting.id, created_at=meeting.created_at)
        row.created_by_user_id = meeting.author_user_id
        _apply_content(row, meeting, deal_id)
        await self._insert(row, _write_errors(meeting))

    async def get(
        self, meeting_id: PartnerMeetingId, *, for_update: bool = False
    ) -> PartnerMeetingRecord:
        statement = (
            select(PartnerMeetingRow, DealRow.deal_code, DealRow.name)
            .join(DealRow, DealRow.id == PartnerMeetingRow.deal_id)
            .where(PartnerMeetingRow.id == meeting_id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update(of=PartnerMeetingRow)
        found = (await self._session.execute(statement)).one_or_none()
        if found is None:
            raise PartnerMeetingNotFoundError(meeting_id)
        row, code, deal_name = found
        return PartnerMeetingRecord(_to_entity(row, code), deal_name)

    async def update(self, meeting: PartnerMeeting) -> None:
        row = await self._find(meeting.id)
        if row is None:
            raise PartnerMeetingNotFoundError(meeting.id)
        code = meeting.subject.deal_code.value
        deal_id = await deal_id_of(self._session, code)
        if deal_id is None:
            raise DealNotFoundError(code)
        _apply_content(row, meeting, deal_id)
        await self._save(
            _write_errors(meeting), not_found=lambda: PartnerMeetingNotFoundError(meeting.id)
        )

    async def delete(self, meeting_id: PartnerMeetingId) -> None:
        row = await self._find(meeting_id)
        if row is None:
            raise PartnerMeetingNotFoundError(meeting_id)
        await self._remove(row, {})

    @staticmethod
    def _conditions(query: PartnerMeetingQuery) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if query.partner is not None:
            conditions.append(_contains(PartnerMeetingRow.partner_company, query.partner))
        if query.deal is not None:
            conditions.append(
                or_(_contains(DealRow.name, query.deal), _contains(DealRow.deal_code, query.deal))
            )
        if query.content is not None:
            conditions.append(_contains(PartnerMeetingRow.content, query.content))
        if query.date_from is not None:
            conditions.append(PartnerMeetingRow.meeting_date >= query.date_from)
        if query.date_to is not None:
            conditions.append(PartnerMeetingRow.meeting_date <= query.date_to)
        if query.author_user_id is not None:
            conditions.append(PartnerMeetingRow.created_by_user_id == query.author_user_id)
        return conditions

    async def search(self, query: PartnerMeetingQuery) -> Sequence[PartnerMeetingRecord]:
        author = aliased(UserRow)
        author_name = func.coalesce(func.nullif(author.display_name, ""), author.login_id)
        text_keys = {
            PartnerMeetingSort.PARTNER: PartnerMeetingRow.partner_company,
            PartnerMeetingSort.DEAL: DealRow.name,
            PartnerMeetingSort.CONTENT: PartnerMeetingRow.content,
            PartnerMeetingSort.AUTHOR: author_name,
        }

        def direction(
            column: ColumnElement[Any] | InstrumentedAttribute[Any],
        ) -> ColumnElement[Any]:
            return column.asc() if query.order is SortOrder.ASC else column.desc()

        date_column, id_column = PartnerMeetingRow.meeting_date, PartnerMeetingRow.id
        if query.sort is PartnerMeetingSort.MEETING_DATE:
            ordering = [direction(date_column), direction(id_column)]
        else:
            key = func.lower(text_keys[query.sort]).collate("C")
            ordering = [direction(key), date_column.desc(), id_column.desc()]
        statement = (
            select(PartnerMeetingRow, DealRow.deal_code, DealRow.name)
            .join(DealRow, DealRow.id == PartnerMeetingRow.deal_id)
            .join(author, author.id == PartnerMeetingRow.created_by_user_id)
        )
        statement = (
            statement.where(*self._conditions(query))
            .order_by(*ordering)
            .offset(query.offset)
            .limit(query.limit)
            .execution_options(populate_existing=True)
        )
        rows = (await self._session.execute(statement)).all()
        return [PartnerMeetingRecord(_to_entity(row, code), name) for row, code, name in rows]

    async def count(self, query: PartnerMeetingQuery) -> int:
        statement = select(func.count(PartnerMeetingRow.id)).join(
            DealRow, DealRow.id == PartnerMeetingRow.deal_id
        )
        return int(await self._session.scalar(statement.where(*self._conditions(query))) or 0)

    async def deal_choices(self, company: str) -> Sequence[PartnerDealChoice]:
        partner = aliased(ContactRow)
        customer = aliased(ContactRow)
        statement = (
            select(DealRow.deal_code, DealRow.name, customer.company)
            .join(DealPartnerRow, and_(DealPartnerRow.deal_id == DealRow.id))
            .join(partner, partner.id == DealPartnerRow.contact_id)
            .join(customer, customer.id == DealRow.customer_id)
            .where(
                DealPartnerRow.unlinked_at.is_(None),
                partner.kind == ContactKind.PARTNER.value,
                func.lower(partner.company) == company.lower(),
            )
            .order_by(func.lower(DealRow.name).collate("C"), DealRow.deal_code)
        )
        return [
            PartnerDealChoice(DealCode(code), name, customer_company)
            for code, name, customer_company in (await self._session.execute(statement)).all()
        ]
