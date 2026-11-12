"""local 모드에서 AD 설정 저장·연결 시험은 InvalidStateError다. 조회(get)는 그대로 둔다."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_MODE_ONLY
from app.domain.auth.credentials import Password
from app.domain.auth.mode import AuthMode
from app.domain.common.errors import InvalidStateError, NotFoundError
from app.domain.directory.settings import DirectorySettingsDraft
from tests.factories_directory import make_directory_connection
from tests.fakes.admin_stack import ADMIN_ACTOR, ADMIN_PASSWORD, OTHER_ADMIN_ACTOR
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
    """local 모드 거절 문구는 고정 문장이다."""
    # when·then: 문구 상수를 읽는다 → 'AD 연동 모드에서만 쓸 수 있습니다.'이다
    assert DIRECTORY_MODE_ONLY == "AD 연동 모드에서만 쓸 수 있습니다."


async def test_update_directory_settings_in_local_mode_is_invalid_state(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """local 모드에서 AD 설정을 저장하면 InvalidStateError이고 AD를 부르지 않는다.

    테스트 코드: IN-037
    """
    # given: 인증 방식이 local이고 AD 설정이 없다
    with pytest.raises(InvalidStateError) as caught:
        await admin.update_settings.execute(
            actor=OTHER_ADMIN_ACTOR,
            draft=_draft(),
            expected_revision=None,
            password=None,
            client_ip=IP,
        )

    assert str(caught.value) == DIRECTORY_MODE_ONLY
    assert directory.discover_calls == []
    assert directory.authenticate_calls == []
    # when·then: AD 설정을 저장한다
    # → 고정 문구의 InvalidStateError이고 AD 호출이 0회이며 행이 생기지 않는다
    async with uow_factory() as uow:
        assert await uow.directory_settings.get() is None


async def test_update_directory_settings_in_local_mode_keeps_an_old_row_unchanged(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """local 모드에서 남아 있던 AD 설정 행은 저장 시도로 바뀌지 않는다.

    테스트 코드: IN-037
    """
    # given: 인증 방식이 local이고 예전 AD 설정 행이 남아 있다
    stored = await seed_directory(uow_factory)

    # when: 올바른 본문으로 저장한다
    with pytest.raises(InvalidStateError):
        await admin.update_settings.execute(
            actor=ADMIN_ACTOR,
            draft=_draft(),
            expected_revision=stored.revision,
            password=Password(ADMIN_PASSWORD),
            client_ip=IP,
        )

    # then: InvalidStateError이고 행은 그대로다
    async with uow_factory() as uow:
        assert await uow.directory_settings.get() == stored


async def test_test_directory_settings_in_local_mode_is_invalid_state(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    """local 모드에서 연결 테스트도 InvalidStateError이고 AD를 부르지 않는다.

    테스트 코드: IN-038
    """
    # when: 연결 테스트한다 (전제: 인증 방식이 local이다)
    with pytest.raises(InvalidStateError) as caught:
        await admin.test_settings.execute(
            actor=ADMIN_ACTOR,
            draft=_draft(),
            password=Password(ADMIN_PASSWORD),
            client_ip=IP,
        )

    # then: 고정 문구의 InvalidStateError이고 AD 탐색 호출이 0회다
    assert str(caught.value) == DIRECTORY_MODE_ONLY
    assert directory.discover_calls == []


async def test_get_directory_settings_in_local_mode_is_still_not_found(admin: AdminStack) -> None:
    """local 모드에서 AD 설정 조회는 막지 않아 설정이 없으면 NotFoundError다.

    테스트 코드: IN-039
    """
    # when·then: AD 설정을 조회한다 → InvalidStateError가 아니라 NotFoundError다
    #   (전제: 인증 방식이 local이고 AD 설정이 없다)
    with pytest.raises(NotFoundError):
        await admin.get_settings.execute()
