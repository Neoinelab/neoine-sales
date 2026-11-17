"""DealCommentRepository Port의 SQLAlchemy 구현.

같은 Deal의 Action만 연결할 수 있다는 규칙은 복합 FK가 보장하고, 제약 위반은 도메인 오류로 바꾼다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import exists, func, select, update

from app.application.deal_comment.views import UnreadCommentCounts
from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal_action.value_objects import DealActionId
from app.domain.deal_comment.entities import DealComment
from app.domain.deal_comment.errors import DealCommentNotFoundError
from app.domain.deal_comment.values import DealCommentId
from app.domain.user.value_objects import UserId
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.deal_keys import deal_id_of
from app.infra.db.models_comment import DealCommentRow
from app.infra.db.models_deal import DealRow

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from sqlalchemy import Select


def _to_row(comment: DealComment, deal_id: int) -> DealCommentRow:
    return DealCommentRow(
        id=comment.id,
        deal_id=deal_id,
        action_id=comment.action_id,
        author_user_id=comment.author_user_id,
        body=comment.body,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        read_at=comment.read_at,
    )


def _to_entity(row: DealCommentRow, deal_code: str) -> DealComment:
    return DealComment(
        id=DealCommentId(row.id),
        deal_code=DealCode(deal_code),
        action_id=None if row.action_id is None else DealActionId(row.action_id),
        author_user_id=UserId(row.author_user_id),
        body=row.body,
        created_at=row.created_at,
        updated_at=row.updated_at,
        read_at=row.read_at,
    )


def _with_code() -> Select[DealCommentRow, str]:
    return select(DealCommentRow, DealRow.deal_code).join(
        DealRow, DealRow.id == DealCommentRow.deal_id
    )


class SqlDealCommentRepository(SqlRepository[DealCommentRow]):
    row_type = DealCommentRow

    async def add(self, comment: DealComment) -> None:
        code = comment.deal_code.value
        deal_id = await deal_id_of(self._session, code)
        if deal_id is None:
            raise DealNotFoundError(code)
        errors: ConstraintErrors = {
            "pk_deal_comments": lambda: AlreadyExistsError("Comment", comment.id),
            "fk_deal_comments_deal_id_deals": lambda: DealNotFoundError(code),
            "fk_deal_comments_action_id_deal_actions": lambda: InvalidReferenceError(
                "Action", comment.action_id
            ),
            "fk_deal_comments_author_user_id_users": lambda: InvalidReferenceError(
                "사용자", comment.author_user_id
            ),
        }
        try:
            await self._insert(_to_row(comment, deal_id), errors)
        except InvalidReferenceError:
            # 여러 FK가 함께 어긋나면 DB가 먼저 보고하는 쪽이 정해져 있지 않다. Deal 없음 우선.
            if not await self._session.scalar(select(exists().where(DealRow.id == deal_id))):
                raise DealNotFoundError(code) from None
            raise

    async def get(self, comment_id: DealCommentId, *, for_update: bool = False) -> DealComment:
        statement = _with_code().where(DealCommentRow.id == comment_id)
        if for_update:
            statement = statement.with_for_update(of=DealCommentRow)
        found = (
            await self._session.execute(statement.execution_options(populate_existing=True))
        ).one_or_none()
        if found is None:
            raise DealCommentNotFoundError(comment_id)
        row, code = found
        return _to_entity(row, code)

    async def list_for_deal(
        self, deal_code: DealCode, *, action_id: DealActionId | None = None
    ) -> Sequence[DealComment]:
        statement = _with_code().where(DealRow.deal_code == deal_code.value)
        if action_id is not None:
            statement = statement.where(DealCommentRow.action_id == action_id)
        statement = statement.order_by(DealCommentRow.created_at.desc(), DealCommentRow.id.desc())
        rows = (
            await self._session.execute(statement.execution_options(populate_existing=True))
        ).all()
        return [_to_entity(row, code) for row, code in rows]

    async def mark_read(
        self, deal_code: DealCode, comment_ids: Sequence[DealCommentId], at: datetime
    ) -> None:
        if not comment_ids:
            return
        deal_id = await deal_id_of(self._session, deal_code.value)
        if deal_id is None:
            return
        statement = (
            update(DealCommentRow)
            .where(
                DealCommentRow.deal_id == deal_id,
                DealCommentRow.id.in_(list(comment_ids)),
                DealCommentRow.read_at.is_(None),
            )
            .values(read_at=at)
            .execution_options(synchronize_session=False)
        )
        await self._session.execute(statement)

    async def unread_counts(self, deal_code: DealCode) -> UnreadCommentCounts:
        statement = (
            select(DealCommentRow.action_id, func.count())
            .join(DealRow, DealRow.id == DealCommentRow.deal_id)
            .where(DealRow.deal_code == deal_code.value, DealCommentRow.read_at.is_(None))
            .group_by(DealCommentRow.action_id)
            .order_by(DealCommentRow.action_id)
        )
        rows = (await self._session.execute(statement)).all()
        by_action = {DealActionId(a): int(n) for a, n in rows if a is not None}
        return UnreadCommentCounts(total=sum(int(n) for _, n in rows), by_action=by_action)

    async def delete(self, comment_id: DealCommentId) -> None:
        row = await self._find(comment_id)
        if row is None:
            raise DealCommentNotFoundError(comment_id)
        await self._remove(row, {})

    async def count_for_action(self, action_id: DealActionId) -> int:
        statement = (
            select(func.count())
            .select_from(DealCommentRow)
            .where(DealCommentRow.action_id == action_id)
        )
        return int(await self._session.scalar(statement) or 0)
