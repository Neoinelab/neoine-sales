from typing import TYPE_CHECKING, TypedDict

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.domain.directory.errors import DirectorySettingsConflictError
from app.domain.directory.settings import DirectoryConnection, SecurityMode, StoredDirectorySettings
from app.domain.user.value_objects import UserId
from app.infra.db.models_auth import DirectorySettingsRow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.application.ports.directory_settings_repository import DirectorySettingsWrite

_ROW_ID = 1


class _DirectoryValues(TypedDict):
    host: str
    port: int
    security: str
    bind_account: None
    bind_password_encrypted: None
    base_dn: str
    user_filter: str
    connect_timeout_seconds: int


def _values(change: DirectorySettingsWrite) -> _DirectoryValues:
    connection = change.connection
    return {
        "host": connection.host,
        "port": connection.port,
        "security": connection.security.value,
        "bind_account": None,
        "bind_password_encrypted": None,
        "base_dn": change.base_dn,
        "user_filter": connection.user_filter,
        "connect_timeout_seconds": connection.connect_timeout_seconds,
    }


def _to_entity(row: DirectorySettingsRow) -> StoredDirectorySettings:
    return StoredDirectorySettings(
        connection=DirectoryConnection(
            host=row.host,
            port=row.port,
            security=SecurityMode(row.security),
            user_filter=row.user_filter,
            connect_timeout_seconds=row.connect_timeout_seconds,
        ),
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

    async def save(self, change: DirectorySettingsWrite) -> StoredDirectorySettings:
        values = _values(change)
        if change.expected_revision is None:
            row = DirectorySettingsRow(
                id=_ROW_ID,
                revision=1,
                updated_at=change.now,
                updated_by_user_id=change.updated_by,
                **values,
            )
            try:
                async with self._session.begin_nested():
                    self._session.add(row)
                    await self._session.flush()
            except IntegrityError as error:
                raise DirectorySettingsConflictError from error
        else:
            statement = (
                update(DirectorySettingsRow)
                .where(
                    DirectorySettingsRow.id == _ROW_ID,
                    DirectorySettingsRow.revision == change.expected_revision,
                )
                .values(
                    revision=change.expected_revision + 1,
                    updated_at=change.now,
                    updated_by_user_id=change.updated_by,
                    **values,
                )
                .returning(DirectorySettingsRow.id)
                .execution_options(synchronize_session=False)
            )
            if (await self._session.execute(statement)).first() is None:
                raise DirectorySettingsConflictError
        stored = await self.get()
        if stored is None:
            raise DirectorySettingsConflictError
        return stored
