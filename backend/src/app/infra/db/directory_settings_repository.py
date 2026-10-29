"""DirectorySettingsRepository Port의 SQLAlchemy 구현. 단일 행(id=1)과 revision 낙관적 잠금."""

from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.domain.common.secret import SealedSecret
from app.domain.directory.errors import DirectorySettingsConflictError
from app.domain.directory.settings import DirectoryConnection, SecurityMode, StoredDirectorySettings
from app.domain.user.value_objects import UserId
from app.infra.db.models_auth import DirectorySettingsRow

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

_ROW_ID = 1


def _values(
    connection: DirectoryConnection, sealed_bind_password: SealedSecret, base_dn: str
) -> dict[str, object]:
    return {
        "host": connection.host,
        "port": connection.port,
        "security": connection.security.value,
        "bind_account": connection.bind_account,
        "bind_password_encrypted": sealed_bind_password.token,
        "base_dn": base_dn,
        "user_filter": connection.user_filter,
        "connect_timeout_seconds": connection.connect_timeout_seconds,
    }


def _to_entity(row: DirectorySettingsRow) -> StoredDirectorySettings:
    return StoredDirectorySettings(
        connection=DirectoryConnection(
            host=row.host,
            port=row.port,
            security=SecurityMode(row.security),
            bind_account=row.bind_account,
            user_filter=row.user_filter,
            connect_timeout_seconds=row.connect_timeout_seconds,
        ),
        sealed_bind_password=SealedSecret(row.bind_password_encrypted),
        base_dn=row.base_dn,
        revision=row.revision,
        updated_at=row.updated_at,
        updated_by=UserId(row.updated_by_user_id) if row.updated_by_user_id is not None else None,
    )


class SqlDirectorySettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> StoredDirectorySettings | None:
        statement = (
            select(DirectorySettingsRow)
            .where(DirectorySettingsRow.id == _ROW_ID)
            .execution_options(populate_existing=True)
        )
        row = (await self._session.scalars(statement)).one_or_none()
        return _to_entity(row) if row else None

    async def save(  # noqa: PLR0913 - 접속 정보·암호문·Base DN + 잠금·감사 값이 모두 필요
        self,
        connection: DirectoryConnection,
        sealed_bind_password: SealedSecret,
        base_dn: str,
        *,
        expected_revision: int | None,
        updated_by: UserId | None,
        now: datetime,
    ) -> StoredDirectorySettings:
        values = _values(connection, sealed_bind_password, base_dn)
        if expected_revision is None:
            await self._create(values, updated_by, now)
        else:
            await self._replace(values, expected_revision, updated_by, now)
        stored = await self.get()
        if stored is None:  # 같은 트랜잭션에서 방금 쓴 행이므로 일어나지 않는다
            raise DirectorySettingsConflictError
        return stored

    async def _create(
        self, values: dict[str, object], updated_by: UserId | None, now: datetime
    ) -> None:
        row = DirectorySettingsRow(
            id=_ROW_ID,
            revision=1,
            updated_at=now,
            updated_by_user_id=updated_by,
            **values,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(row)
                await self._session.flush()
        except IntegrityError as error:
            raise DirectorySettingsConflictError from error

    async def _replace(
        self,
        values: dict[str, object],
        expected_revision: int,
        updated_by: UserId | None,
        now: datetime,
    ) -> None:
        statement = (
            update(DirectorySettingsRow)
            .where(
                DirectorySettingsRow.id == _ROW_ID,
                DirectorySettingsRow.revision == expected_revision,
            )
            .values(
                revision=expected_revision + 1,
                updated_at=now,
                updated_by_user_id=updated_by,
                **values,
            )
            .returning(DirectorySettingsRow.id)
            .execution_options(synchronize_session=False)
        )
        if (await self._session.execute(statement)).first() is None:
            raise DirectorySettingsConflictError
