"""SQL Repository 공통 동작: 조회, 페이지, SAVEPOINT 저장과 제약 위반의 도메인 오류 변환."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.application.ports.pagination import check_page
from app.infra.db.models import AuditColumns

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

ConstraintErrors = Mapping[str, Callable[[], Exception]]


class SavepointWriter:
    """세션 하나 위에서 SAVEPOINT로 감싼 쓰기. 제약 위반을 매핑된 도메인 오류로 바꾼다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _insert(self, row: object, constraint_errors: ConstraintErrors) -> None:
        await self._flush(constraint_errors, add=row)

    async def _save(
        self, constraint_errors: ConstraintErrors, *, not_found: Callable[[], Exception]
    ) -> None:
        """갱신 flush. 읽은 뒤 동시 삭제로 UPDATE가 0행이면 not_found 오류로 바꾼다."""
        await self._flush(constraint_errors, not_found=not_found)

    async def _remove(self, row: object, constraint_errors: ConstraintErrors) -> None:
        """물리 삭제. 참조 제약(FK RESTRICT) 위반은 매핑된 도메인 오류로 바꾼다."""
        await self._flush(constraint_errors, delete=row)

    async def _flush(
        self,
        constraint_errors: ConstraintErrors,
        *,
        add: object | None = None,
        delete: object | None = None,
        not_found: Callable[[], Exception] | None = None,
    ) -> None:
        async def work() -> None:
            if add is not None:
                self._session.add(add)
            if delete is not None:
                await self._session.delete(delete)

        await self._atomic(constraint_errors, work, not_found=not_found)

    async def _atomic(
        self,
        constraint_errors: ConstraintErrors,
        work: Callable[[], Awaitable[None]],
        *,
        not_found: Callable[[], Exception] | None = None,
    ) -> None:
        """work와 flush를 한 SAVEPOINT 안에서 실행한다(제약 위반이 나도 바깥 트랜잭션은 온전하다).

        work 안에서 `await session.flush()`를 여러 번 불러 쓰기 순서를 정할 수 있다.
        """
        try:
            async with self._session.begin_nested():
                await work()
                await self._session.flush()
        except StaleDataError as error:
            if not_found is not None:
                raise not_found() from error
            raise
        except IntegrityError as error:
            message = str(error.orig)
            for constraint, make_error in constraint_errors.items():
                if constraint in message:
                    raise make_error() from error
            raise


class SqlRepository[RowT: AuditColumns](SavepointWriter):
    row_type: type[RowT]

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
