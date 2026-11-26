from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select, update

from app.application.ports.directory_settings_repository import DirectorySettingsWrite
from app.infra.db.directory_settings_repository import SqlDirectorySettingsRepository
from app.infra.db.models_auth import DirectorySettingsRow
from tests.factories import NOW
from tests.factories_auth import BASE_DN
from tests.factories_directory import make_directory_connection

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_insert_and_update_write_null_credentials(session: AsyncSession) -> None:
    repository = SqlDirectorySettingsRepository(session)
    connection = make_directory_connection()
    await repository.save(
        DirectorySettingsWrite(
            connection=connection,
            base_dn=BASE_DN,
            expected_revision=None,
            updated_by=None,
            now=NOW,
        )
    )
    columns = select(
        DirectorySettingsRow.bind_account, DirectorySettingsRow.bind_password_encrypted
    )
    assert (await session.execute(columns)).one() == (None, None)
    await session.execute(
        update(DirectorySettingsRow).values(
            bind_account="old-service",
            bind_password_encrypted="legacy-token",  # noqa: S106 - 이전 암호문 더미,
        )
    )
    stored = await repository.get()
    assert stored is not None
    await repository.save(
        DirectorySettingsWrite(
            connection=connection,
            base_dn=BASE_DN,
            expected_revision=1,
            updated_by=None,
            now=NOW,
        )
    )
    assert (await session.execute(columns)).one() == (None, None)
