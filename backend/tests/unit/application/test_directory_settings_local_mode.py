"""local 모드에서 AD 설정 저장·연결 시험은 InvalidStateError다 (AC-13). 조회(get)는 그대로 둔다."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_MODE_ONLY
from app.domain.auth.credentials import Password
from app.domain.auth.mode import AuthMode
from app.domain.common.errors import InvalidStateError, NotFoundError
from app.domain.directory.settings import DirectorySettingsDraft
from tests.factories_directory import make_directory_connection
from tests.fakes.admin_stack import ADMIN_ACTOR, ADMIN_PASSWORD, DEV_ACTOR
from tests.support.auth_seed import seed_auth_mode, seed_directory

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.directory import FakeDirectoryAuthenticator

IP = "10.0.0.1"


def _draft() -> DirectorySettingsDraft:
    return DirectorySettingsDraft(
        connection=make_directory_connection(host="dc2.corp.test"),
        bind_password=Password("New-bind-pw-2!"),
    )


@pytest.fixture(autouse=True)
async def _local_mode(uow_factory: UnitOfWorkFactory) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)


def test_the_directory_mode_only_message_is_a_fixed_sentence() -> None:
    assert DIRECTORY_MODE_ONLY == "AD 연동 모드에서만 쓸 수 있습니다."


async def test_update_directory_settings_in_local_mode_is_invalid_state(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    with pytest.raises(InvalidStateError) as caught:
        await admin.update_settings.execute(
            actor=DEV_ACTOR,
            draft=_draft(),
            expected_revision=None,
            password=None,
            client_ip=IP,
        )

    assert str(caught.value) == DIRECTORY_MODE_ONLY
    assert directory.discover_calls == []
    assert directory.authenticate_calls == []
    async with uow_factory() as uow:
        assert await uow.directory_settings.get() is None


async def test_update_directory_settings_in_local_mode_keeps_an_old_row_unchanged(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    stored = await seed_directory(uow_factory)

    with pytest.raises(InvalidStateError):
        await admin.update_settings.execute(
            actor=ADMIN_ACTOR,
            draft=_draft(),
            expected_revision=stored.revision,
            password=Password(ADMIN_PASSWORD),
            client_ip=IP,
        )

    async with uow_factory() as uow:
        assert await uow.directory_settings.get() == stored


async def test_test_directory_settings_in_local_mode_is_invalid_state(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    with pytest.raises(InvalidStateError) as caught:
        await admin.test_settings.execute(
            actor=ADMIN_ACTOR,
            draft=_draft(),
            password=Password(ADMIN_PASSWORD),
            client_ip=IP,
        )

    assert str(caught.value) == DIRECTORY_MODE_ONLY
    assert directory.discover_calls == []


async def test_get_directory_settings_in_local_mode_is_still_not_found(admin: AdminStack) -> None:
    with pytest.raises(NotFoundError):
        await admin.get_settings.execute()
