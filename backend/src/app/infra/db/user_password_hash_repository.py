"""UserPasswordHashRepository Port의 SQLAlchemy 구현. 사용자 id 하나에 행 하나(upsert)."""

from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.domain.auth.password_hash import PasswordHash
from app.domain.user.errors import UserNotFoundError
from app.infra.db.models_auth import UserPasswordHashRow

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.user.value_objects import UserId

_USER_FK = "fk_user_password_hashes_user_id_users"


class SqlUserPasswordHashRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UserId) -> PasswordHash | None:
        statement = select(UserPasswordHashRow.password_hash).where(
            UserPasswordHashRow.user_id == user_id
        )
        stored = await self._session.scalar(statement)
        return PasswordHash(stored) if stored is not None else None

    async def save(self, user_id: UserId, password_hash: PasswordHash, now: datetime) -> None:
        values = {"password_hash": password_hash.encoded, "updated_at": now}
        statement = insert(UserPasswordHashRow).values(user_id=user_id, **values)
        try:
            async with self._session.begin_nested():
                await self._session.execute(
                    statement.on_conflict_do_update(index_elements=["user_id"], set_=values)
                )
        except IntegrityError as error:
            if _USER_FK in str(error.orig):  # 해시를 저장하는 동안 사용자가 삭제됐다
                raise UserNotFoundError(user_id) from error
            raise

    async def delete(self, user_id: UserId) -> None:
        await self._session.execute(
            delete(UserPasswordHashRow).where(UserPasswordHashRow.user_id == user_id)
        )
