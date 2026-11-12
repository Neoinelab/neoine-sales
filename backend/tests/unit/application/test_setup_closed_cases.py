"""재직 admin이 있으면 모든 최초 설정 경로가 닫힌다: SU-039."""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import SETUP_CLOSED
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.factories_directory import make_directory_settings
from tests.support.auth_seed import (
    active_admin_logins,
    seed_auth_mode,
    seed_setup_prerequisites,
    seed_storage,
    seed_user,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.storage_stack import StorageStack

IP = "10.0.0.9"
Operation = Callable[["AuthStack", "StorageStack"], Awaitable[None]]


async def _register_directory(auth: AuthStack, _: StorageStack) -> None:
    await auth.register_directory.execute(make_directory_settings(host="dc9.corp.test"))


async def _register_storage(_: AuthStack, storage: StorageStack) -> None:
    await storage.register_setup.execute("/data/new")


async def _register_malformed_storage(_: AuthStack, storage: StorageStack) -> None:
    await storage.register_setup.execute("relative")


async def _test_storage(_: AuthStack, storage: StorageStack) -> None:
    await storage.test_setup.execute("/data/new")


async def _test_malformed_storage(_: AuthStack, storage: StorageStack) -> None:
    await storage.test_setup.execute("relative")


async def _setup_ad_admin(auth: AuthStack, _: StorageStack) -> None:
    auth.directory.add_account("mallory", "pw-mallory")
    await auth.setup.execute(login_id="mallory", password=Password("pw-mallory"), client_ip=IP)


async def _choose_mode(auth: AuthStack, _: StorageStack) -> None:
    await auth.choose_mode.execute(AuthMode.LOCAL)


OPERATIONS: dict[str, Operation] = {
    "directory": _register_directory,
    "storage": _register_storage,
    "storage-malformed": _register_malformed_storage,
    "storage-test": _test_storage,
    "storage-test-malformed": _test_malformed_storage,
    "admin-ad": _setup_ad_admin,
    "mode": _choose_mode,
}


@pytest.mark.parametrize("name", list(OPERATIONS))
async def test_every_setup_operation_is_closed_and_changes_nothing(
    auth: AuthStack, storage: StorageStack, uow_factory: UnitOfWorkFactory, name: str
) -> None:
    """재직 admin이 있으면 모든 최초 설정 경로가 닫힘 오류이고 AD를 부르지 않으며 바뀌는 것이 없다.

    테스트 코드: SU-039
    """
    # given: 재직 admin이 있고 AD·저장 위치 설정이 있다
    await seed_setup_prerequisites(uow_factory)
    await seed_user(uow_factory, "boss", Role.ADMIN)
    async with uow_factory() as uow:
        directory_before = await uow.directory_settings.get()
        storage_before = await uow.storage_settings.get()

    # when: AD 서버·저장 위치 등록, 쓰기 테스트, 첫 admin 등록 등(틀린 경로 포함)을 부른다
    with pytest.raises(InvalidStateError) as caught:
        await OPERATIONS[name](auth, storage)

    # then: 닫힘 문구이고 AD 호출이 없으며 설정·사용자(mallory 없음)가 그대로다
    assert str(caught.value) == SETUP_CLOSED
    assert auth.directory.discover_calls == []
    assert auth.directory.authenticate_calls == []
    async with uow_factory() as uow:
        assert await uow.directory_settings.get() == directory_before
        assert await uow.storage_settings.get() == storage_before
        assert await uow.users.get_active_by_login_id(LoginId("mallory")) is None
        assert await uow.auth_settings.get() is None
    assert await active_admin_logins(uow_factory) == ["boss"]
    assert (await auth.status.execute()).needs_admin_setup is False


@pytest.mark.parametrize("name", list(OPERATIONS))
async def test_every_setup_operation_stays_closed_when_the_setting_rows_are_gone(
    auth: AuthStack, storage: StorageStack, uow_factory: UnitOfWorkFactory, name: str
) -> None:
    """AD·저장 위치 설정 행이 지워져 있어도 재직 admin이 있으면 닫혀 있다.

    테스트 코드: SU-039
    """
    # given: 재직 admin만 있고 AD 설정·저장 위치 행이 없다
    await seed_user(uow_factory, "boss", Role.ADMIN)

    # when: 최초 설정 경로를 부른다
    with pytest.raises(InvalidStateError) as caught:
        await OPERATIONS[name](auth, storage)

    # then: 닫힘 문구이고 AD를 부르지 않았으며 설정 행이 새로 생기지 않았다
    assert str(caught.value) == SETUP_CLOSED
    assert auth.directory.discover_calls == []
    assert auth.directory.authenticate_calls == []
    async with uow_factory() as uow:
        assert await uow.directory_settings.get() is None
        assert await uow.storage_settings.get() is None


async def test_the_local_first_admin_registration_is_closed_too(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """올바른 local 입력의 첫 admin 등록도 닫혀 있다.

    테스트 코드: SU-039
    """
    # given: local 방식에 저장 위치가 있고 재직 admin이 있다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    await seed_storage(uow_factory)
    await seed_user(uow_factory, "boss", Role.ADMIN)

    # when: 올바른 local 입력으로 첫 admin을 등록한다
    with pytest.raises(InvalidStateError) as caught:
        await auth.setup.execute(
            login_id="mallory",
            password=Password("Passw0rd-ok"),
            client_ip=IP,
            display_name="침입자",
        )

    # then: 닫힘 문구이고 mallory는 없다
    assert str(caught.value) == SETUP_CLOSED
    assert await active_admin_logins(uow_factory) == ["boss"]
