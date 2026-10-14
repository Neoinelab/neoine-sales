"""SessionRepository Port의 SQLAlchemy 구현. 세션은 users.id를 FK로 가리킨다."""

from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.domain.auth.principal import Principal, Role
from app.domain.auth.session import AuthSession, SessionId
from app.domain.common.errors import AlreadyExistsError, NotFoundError
from app.domain.user.errors import UserNotFoundError
from app.domain.user.value_objects import UserId
from app.infra.db.models import AuthSessionRow
from app.infra.db.models_auth import UserRow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_USER_FK = "fk_auth_sessions_user_id_users"


def _to_entity(row: AuthSessionRow, login_id: str) -> AuthSession:
    return AuthSession(
        id=SessionId(row.id),
        principal=Principal(UserId(row.user_id), login_id, row.email, row.name, Role(row.role)),
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
            user_id=principal.user_id,
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
            if _USER_FK in str(error.orig):  # 세션을 만드는 동안 사용자가 삭제됐다
                raise UserNotFoundError(principal.user_id) from error
            raise AlreadyExistsError("세션", session.id) from error

    async def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        statement = (
            select(AuthSessionRow, UserRow.login_id)
            .join(UserRow, UserRow.id == AuthSessionRow.user_id)
            .where(AuthSessionRow.token_hash == token_hash)
            .execution_options(populate_existing=True)
        )
        found = (await self._session.execute(statement)).one_or_none()
        return _to_entity(found[0], found[1]) if found else None

    async def update(self, session: AuthSession) -> None:
        row = await self._session.get(AuthSessionRow, session.id, populate_existing=True)
        if row is None:
            raise NotFoundError("세션", session.id)
        row.revoked_at = session.revoked_at
        await self._session.flush()

    async def delete_all_for_user(self, user_id: UserId) -> int:
        statement = (
            delete(AuthSessionRow)
            .where(AuthSessionRow.user_id == user_id)
            .returning(AuthSessionRow.id)
            .execution_options(synchronize_session=False)
        )
        return len((await self._session.execute(statement)).all())
