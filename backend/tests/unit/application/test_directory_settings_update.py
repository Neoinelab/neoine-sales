from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidValueError, NotFoundError
from app.domain.common.secret import SealedSecret
from app.domain.directory.errors import DirectorySettingsConflictError
from app.domain.directory.settings import DirectorySettingsDraft
from tests.factories_directory import make_directory_settings
from tests.fakes.admin_stack import ADMIN_ACTOR, OTHER_ADMIN_ACTOR
from tests.support.auth_seed import seed_directory

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.directory import FakeDirectoryAuthenticator


async def tested_draft(admin: AdminStack) -> DirectorySettingsDraft:
    settings = make_directory_settings(host="other.corp.test")
    result = await admin.test_settings.execute(actor=ADMIN_ACTOR, settings=settings)
    assert result.test_token
    return DirectorySettingsDraft(settings.connection, SealedSecret(result.test_token))


# 테스트 코드: IN-022
async def test_save_uses_proof_without_repeating_bind_and_increments_revision(
    admin: AdminStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
) -> None:
    await seed_directory(uow_factory)
    draft = await tested_draft(admin)
    saved = await admin.update_settings.execute(actor=ADMIN_ACTOR, draft=draft, expected_revision=1)
    assert len(directory.discover_calls) == 1
    assert directory.authenticate_calls == []
    assert saved.connection == draft.connection
    assert saved.revision == 2
    assert saved.updated_by == ADMIN_ACTOR.user_id
    async with uow_factory() as uow:
        assert await uow.directory_settings.get() == saved


# 테스트 코드: IN-025
@pytest.mark.parametrize("expected", [None, 0, 2])
# 테스트 코드: IN-025
async def test_stale_revision_keeps_the_previous_row(
    admin: AdminStack,
    uow_factory: UnitOfWorkFactory,
    expected: int | None,
) -> None:
    previous = await seed_directory(uow_factory)
    draft = await tested_draft(admin)
    with pytest.raises(DirectorySettingsConflictError):
        await admin.update_settings.execute(
            actor=ADMIN_ACTOR, draft=draft, expected_revision=expected
        )
    async with uow_factory() as uow:
        assert await uow.directory_settings.get() == previous


# 테스트 코드: IN-026, IN-027
async def test_null_revision_creates_and_integer_revision_requires_existing_row(
    admin: AdminStack,
) -> None:
    draft = await tested_draft(admin)
    with pytest.raises(NotFoundError):
        await admin.update_settings.execute(actor=ADMIN_ACTOR, draft=draft, expected_revision=1)
    saved = await admin.update_settings.execute(
        actor=ADMIN_ACTOR, draft=draft, expected_revision=None
    )
    assert saved.revision == 1


async def test_another_admin_cannot_reuse_the_proof(admin: AdminStack) -> None:
    draft = await tested_draft(admin)
    with pytest.raises(InvalidValueError):
        await admin.update_settings.execute(
            actor=OTHER_ADMIN_ACTOR,
            draft=draft,
            expected_revision=None,
        )
