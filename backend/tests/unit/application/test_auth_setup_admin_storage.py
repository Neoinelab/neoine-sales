"""최초 admin 지정(SetupFirstAdmin)은 AD 설정 다음으로 저장 위치를 확인한다 (P2b AC-04)."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_FIRST, STORAGE_FIRST
from app.domain.auth.credentials import Password
from app.domain.common.errors import InvalidStateError
from tests.support.auth_seed import active_admin_logins, seed_directory, seed_storage

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

IP = "10.0.0.1"


async def _setup(auth: AuthStack) -> None:
    await auth.setup_admin.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)


def test_the_storage_first_message_is_the_fixed_sentence() -> None:
    assert STORAGE_FIRST == "파일 저장 위치를 먼저 설정하세요."


async def test_setup_admin_without_storage_is_rejected_with_the_storage_first_message(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)

    with pytest.raises(InvalidStateError) as caught:
        await _setup(auth)

    assert str(caught.value) == STORAGE_FIRST


async def test_setup_admin_without_storage_registers_nobody_and_never_asks_the_directory(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_directory(uow_factory)

    with pytest.raises(InvalidStateError):
        await _setup(auth)

    assert await active_admin_logins(uow_factory) == []
    assert auth.directory.authenticate_calls == []
    assert uow.sessions._items == {}


async def test_setup_admin_without_storage_releases_the_login_attempt_counters(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """'AD 먼저'와 같은 경로: 설정 순서 오류는 로그인 실패로 세지 않는다."""
    await seed_directory(uow_factory)

    for _ in range(3):
        with pytest.raises(InvalidStateError):
            await _setup(auth)

    assert uow.login_failures._items == {}


async def test_setup_admin_without_directory_still_reports_the_directory_first_message(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """AD 설정도 저장 위치도 없으면 순서상 먼저인 AD 안내가 나온다."""
    with pytest.raises(InvalidStateError) as caught:
        await _setup(auth)

    assert str(caught.value) == DIRECTORY_FIRST


async def test_setup_admin_with_storage_but_without_directory_reports_directory_first(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_storage(uow_factory)

    with pytest.raises(InvalidStateError) as caught:
        await _setup(auth)

    assert str(caught.value) == DIRECTORY_FIRST


async def test_setup_admin_succeeds_once_directory_and_storage_exist(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    await seed_storage(uow_factory)

    await _setup(auth)

    assert await active_admin_logins(uow_factory) == ["kim"]
