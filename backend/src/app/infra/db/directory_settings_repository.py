"""DirectorySettingsRepository Port의 SQLAlchemy 구현. 단일 행(id=1)과 revision 낙관적 잠금."""

from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.domain.directory.errors import DirectorySettingsConflictError
from app.domain.directory.settings import DirectorySettings, DirectoryUrl, StoredDirectorySettings
from app.domain.user.value_objects import UserId
from app.infra.db.models_auth import DirectorySettingsRow

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

_ROW_ID = 1


def _values(settings: DirectorySettings) -> dict[str, object]:
    return {
        "server_urls": [url.uri for url in settings.server_urls],
        "use_starttls": settings.use_starttls,
        "ca_cert_pem": settings.ca_cert_pem,
        "bind_template": settings.bind_template,
        "base_dn": settings.base_dn,
        "user_filter": settings.user_filter,
        "display_name_attribute": settings.display_name_attribute,
        "email_attribute": settings.email_attribute,
        "connect_timeout_seconds": settings.connect_timeout_seconds,
        "receive_timeout_seconds": settings.receive_timeout_seconds,
    }


def _to_entity(row: DirectorySettingsRow) -> StoredDirectorySettings:
    return StoredDirectorySettings(
        settings=DirectorySettings(
            server_urls=tuple(DirectoryUrl.parse(str(url)) for url in row.server_urls),
            use_starttls=row.use_starttls,
            ca_cert_pem=row.ca_cert_pem,
            bind_template=row.bind_template,
            base_dn=row.base_dn,
            user_filter=row.user_filter,
            display_name_attribute=row.display_name_attribute,
            email_attribute=row.email_attribute,
            connect_timeout_seconds=row.connect_timeout_seconds,
            receive_timeout_seconds=row.receive_timeout_seconds,
        ),
        revision=row.revision,
        updated_at=row.updated_at,
        updated_by=UserId(row.updated_by_user_id) if row.updated_by_user_id else None,
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

    async def save(
        self,
        settings: DirectorySettings,
        *,
        expected_revision: int | None,
        updated_by: UserId | None,
        now: datetime,
    ) -> StoredDirectorySettings:
        if expected_revision is None:
            await self._create(settings, updated_by, now)
        else:
            await self._replace(settings, expected_revision, updated_by, now)
        stored = await self.get()
        if stored is None:  # 같은 트랜잭션에서 방금 쓴 행이므로 일어나지 않는다
            raise DirectorySettingsConflictError
        return stored

    async def _create(
        self, settings: DirectorySettings, updated_by: UserId | None, now: datetime
    ) -> None:
        row = DirectorySettingsRow(
            id=_ROW_ID,
            revision=1,
            updated_at=now,
            updated_by_user_id=updated_by,
            **_values(settings),
        )
        try:
            async with self._session.begin_nested():
                self._session.add(row)
                await self._session.flush()
        except IntegrityError as error:
            raise DirectorySettingsConflictError from error

    async def _replace(
        self,
        settings: DirectorySettings,
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
                **_values(settings),
            )
            .returning(DirectorySettingsRow.id)
            .execution_options(synchronize_session=False)
        )
        if (await self._session.execute(statement)).first() is None:
            raise DirectorySettingsConflictError
