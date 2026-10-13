"""SQL Repository 공통 동작: 조회, 페이지, SAVEPOINT 저장과 제약 위반의 도메인 오류 변환."""

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, select
from sqlalchemy.exc import IntegrityError

from app.application.ports.pagination import check_page
from app.infra.db.models import AuditColumns

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

ConstraintErrors = Mapping[str, Callable[[], Exception]]


class SqlRepository[RowT: AuditColumns]:
    row_type: type[RowT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _find(self, entity_id: UUID) -> RowT | None:
        return await self._session.get(self.row_type, entity_id, populate_existing=True)

    async def _page(
        self, offset: int, limit: int, *, condition: ColumnElement[bool] | None = None
    ) -> Sequence[RowT]:
        """created_at, id 순 페이지. condition이 있으면 추가 WHERE 조건으로 함께 건다."""
        check_page(offset, limit)
        statement = select(self.row_type).order_by(self.row_type.created_at, self.row_type.id)
        if condition is not None:
            statement = statement.where(condition)
        statement = statement.offset(offset).limit(limit).execution_options(populate_existing=True)
        return (await self._session.scalars(statement)).all()

    async def _insert(self, row: RowT, constraint_errors: ConstraintErrors) -> None:
        await self._flush(constraint_errors, add=row)

    async def _save(self, constraint_errors: ConstraintErrors) -> None:
        await self._flush(constraint_errors)

    async def _remove(self, row: RowT, constraint_errors: ConstraintErrors) -> None:
        """물리 삭제. 참조 제약(FK RESTRICT) 위반은 매핑된 도메인 오류로 바꾼다."""
        await self._flush(constraint_errors, delete=row)

    async def _flush(
        self,
        constraint_errors: ConstraintErrors,
        *,
        add: RowT | None = None,
        delete: RowT | None = None,
    ) -> None:
        """SAVEPOINT 안에서 flush해, 제약 위반이 나도 바깥 트랜잭션(세션)이 오염되지 않게 한다."""
        try:
            async with self._session.begin_nested():
                if add is not None:
                    self._session.add(add)
                if delete is not None:
                    await self._session.delete(delete)
                await self._session.flush()
        except IntegrityError as error:
            message = str(error.orig)
            for constraint, make_error in constraint_errors.items():
                if constraint in message:
                    raise make_error() from error
            raise
