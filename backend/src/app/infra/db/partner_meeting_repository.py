"""PartnerMeetingRepository Port의 SQLAlchemy 구현. 작성자 존재는 DB 제약이 보장한다."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import aliased

from app.application.ports.deal_repository import SortOrder
from app.application.ports.partner_meeting_repository import PartnerMeetingSort
from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.partner_meeting.entities import PartnerMeeting
from app.domain.partner_meeting.errors import PartnerMeetingNotFoundError
from app.domain.partner_meeting.values import MeetingContent, PartnerMeetingId
from app.domain.user.value_objects import UserId
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.like import LIKE_ESCAPE, like_pattern
from app.infra.db.models_auth import UserRow
from app.infra.db.models_meeting import PartnerMeetingRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.orm import InstrumentedAttribute

    from app.application.ports.partner_meeting_repository import PartnerMeetingQuery


def _to_entity(row: PartnerMeetingRow) -> PartnerMeeting:
    return PartnerMeeting(
        id=PartnerMeetingId(row.id),
        partner_company=row.partner_company,
        meeting_date=row.meeting_date,
        content=MeetingContent(row.content),
        author_user_id=UserId(row.created_by_user_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _apply_content(row: PartnerMeetingRow, meeting: PartnerMeeting) -> None:
    row.partner_company = meeting.partner_company
    row.meeting_date = meeting.meeting_date
    row.content = meeting.content.value
    row.updated_at = meeting.updated_at


def _write_errors(meeting: PartnerMeeting) -> ConstraintErrors:
    return {
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
        row = PartnerMeetingRow(id=meeting.id, created_at=meeting.created_at)
        row.created_by_user_id = meeting.author_user_id
        _apply_content(row, meeting)
        await self._insert(row, _write_errors(meeting))

    async def get(
        self, meeting_id: PartnerMeetingId, *, for_update: bool = False
    ) -> PartnerMeeting:
        statement = (
            select(PartnerMeetingRow)
            .where(PartnerMeetingRow.id == meeting_id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update(of=PartnerMeetingRow)
        row = (await self._session.execute(statement)).scalar_one_or_none()
        if row is None:
            raise PartnerMeetingNotFoundError(meeting_id)
        return _to_entity(row)

    async def update(self, meeting: PartnerMeeting) -> None:
        row = await self._find(meeting.id)
        if row is None:
            raise PartnerMeetingNotFoundError(meeting.id)
        _apply_content(row, meeting)
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
        if query.content is not None:
            conditions.append(_contains(PartnerMeetingRow.content, query.content))
        if query.date_from is not None:
            conditions.append(PartnerMeetingRow.meeting_date >= query.date_from)
        if query.date_to is not None:
            conditions.append(PartnerMeetingRow.meeting_date <= query.date_to)
        if query.author_user_id is not None:
            conditions.append(PartnerMeetingRow.created_by_user_id == query.author_user_id)
        return conditions

    async def search(self, query: PartnerMeetingQuery) -> Sequence[PartnerMeeting]:
        author = aliased(UserRow)
        author_name = func.coalesce(func.nullif(author.display_name, ""), author.login_id)
        text_keys = {
            PartnerMeetingSort.PARTNER: PartnerMeetingRow.partner_company,
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
        statement = select(PartnerMeetingRow).join(
            author, author.id == PartnerMeetingRow.created_by_user_id
        )
        statement = (
            statement.where(*self._conditions(query))
            .order_by(*ordering)
            .offset(query.offset)
            .limit(query.limit)
            .execution_options(populate_existing=True)
        )
        rows = (await self._session.execute(statement)).scalars().all()
        return [_to_entity(row) for row in rows]

    async def count(self, query: PartnerMeetingQuery) -> int:
        statement = select(func.count(PartnerMeetingRow.id))
        return int(await self._session.scalar(statement.where(*self._conditions(query))) or 0)
