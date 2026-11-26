from typing import TYPE_CHECKING

import pytest

from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from app.domain.common.errors import NotFoundError
from tests.factories_directory import make_directory_settings
from tests.fakes.admin_stack import ADMIN_ACTOR
from tests.support.auth_seed import seed_directory

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.directory import FakeDirectoryAuthenticator


# 테스트 코드: IN-001
async def test_get_returns_connection_without_credentials(
    admin: AdminStack,
    uow_factory: UnitOfWorkFactory,
) -> None:
    stored = await seed_directory(uow_factory)
    found = await admin.get_settings.execute()
    assert found == stored
    assert "credentials" not in repr(found)


# 테스트 코드: IN-003
async def test_get_without_a_row_is_not_found(admin: AdminStack) -> None:
    with pytest.raises(NotFoundError):
        await admin.get_settings.execute()


# 테스트 코드: IN-004
async def test_connection_test_uses_transient_credentials_and_never_saves(
    admin: AdminStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
) -> None:
    previous = await seed_directory(uow_factory)
    settings = make_directory_settings(host="other.corp.test", bind_account="operator")
    result = await admin.test_settings.execute(actor=ADMIN_ACTOR, settings=settings)
    assert result.success
    assert result.test_token
    assert directory.discover_calls == [settings]
    assert directory.authenticate_calls == []
    async with uow_factory() as uow:
        assert await uow.directory_settings.get() == previous


@pytest.mark.parametrize(
    "stage",
    [
        VerificationStage.CONNECT,
        VerificationStage.TLS,
        VerificationStage.SERVICE_BIND,
        VerificationStage.BASE_DN,
    ],
)
# 테스트 코드: IN-006, IN-007
async def test_failed_connection_returns_sanitized_result_without_a_proof(
    admin: AdminStack,
    directory: FakeDirectoryAuthenticator,
    stage: VerificationStage,
) -> None:
    directory.discover_fails_with = DirectoryUnavailableError("private-banner", stage=stage)
    result = await admin.test_settings.execute(
        actor=ADMIN_ACTOR, settings=make_directory_settings()
    )
    assert not result.success
    assert result.stage == stage
    assert result.test_token is None
    assert "private-banner" not in repr(result)
    assert directory.authenticate_calls == []
