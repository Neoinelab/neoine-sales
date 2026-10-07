"""SessionRepository Port의 SQLAlchemy 구현."""

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.auth.principal import Principal, Role
from app.domain.auth.session import AuthSession, SessionId
from app.domain.common.errors import AlreadyExistsError, NotFoundError
from app.infra.db.models import AuthSessionRow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _to_entity(row: AuthSessionRow) -> AuthSession:
    return AuthSession(
        id=SessionId(row.id),
        principal=Principal(row.subject, row.email, row.name, Role(row.role)),
        created_at=row.created_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
    )


class SqlSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, session: AuthSession, token_hash: str) -> None:
        principal = session.principal
        row = AuthSessionRow(
            id=session.id,
            token_hash=token_hash,
            subject=principal.subject,
            email=principal.email,
            name=principal.name,
            role=principal.role.value,
            created_at=session.created_at,
            expires_at=session.expires_at,
            revoked_at=session.revoked_at,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(row)
                await self._session.flush()
        except IntegrityError as error:
            raise AlreadyExistsError("세션", session.id) from error

    async def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        statement = (
            select(AuthSessionRow)
            .where(AuthSessionRow.token_hash == token_hash)
            .execution_options(populate_existing=True)
        )
        row = (await self._session.scalars(statement)).one_or_none()
        return _to_entity(row) if row else None

    async def update(self, session: AuthSession) -> None:
        row = await self._session.get(AuthSessionRow, session.id, populate_existing=True)
        if row is None:
            raise NotFoundError("세션", session.id)
        row.revoked_at = session.revoked_at
        await self._session.flush()
