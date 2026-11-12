"""최초 설정 1단계 인증 방식 선택(ChooseSetupAuthMode): SU-007~SU-009."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import SETUP_CLOSED
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.support.auth_seed import seed_auth_mode, seed_directory, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FixedClock


async def _stored_mode(uow_factory: UnitOfWorkFactory) -> AuthMode | None:
    async with uow_factory() as uow:
        stored = await uow.auth_settings.get()
    return None if stored is None else stored.mode


async def _stored_updated_at(uow_factory: UnitOfWorkFactory) -> datetime | None:
    async with uow_factory() as uow:
        stored = await uow.auth_settings.get()
    return None if stored is None else stored.updated_at


async def test_the_mode_can_be_chosen_and_changed_before_the_first_admin(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """admin 전에는 인증 방식을 고르고 다시 바꿀 수 있고, 고를 때마다 서버 시각이 기록된다.

    테스트 코드: SU-007
    """
    # given: 재직 admin이 없다
    first = await auth.choose_mode.execute(AuthMode.LOCAL)
    first_at = clock.now()
    assert await _stored_updated_at(uow_factory) == first_at
    clock.advance(120)
    # when: local을 고르고 시간이 흐른 뒤 ad를 고른다
    second = await auth.choose_mode.execute(AuthMode.AD)

    # then: 두 번 모두 저장되고 저장된 방식은 ad이며 수정 시각은 두 번째 선택 시각이다
    assert first.mode is AuthMode.LOCAL
    assert second.mode is AuthMode.AD
    assert await _stored_mode(uow_factory) is AuthMode.AD
    assert await _stored_updated_at(uow_factory) == first_at + timedelta(seconds=120)


async def test_choosing_local_keeps_the_saved_directory_settings(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """local을 골라도 저장된 AD 설정은 지워지지 않는다.

    테스트 코드: SU-008
    """
    # given: admin 없이 AD 설정이 저장되어 있다
    stored = await seed_directory(uow_factory)

    # when: 인증 방식 local을 고른다
    await auth.choose_mode.execute(AuthMode.LOCAL)

    # then: AD 설정 행은 그대로이며 유효 방식은 local이다
    async with uow_factory() as uow:
        assert await uow.directory_settings.get() == stored
    assert (await auth.status.execute()).auth_mode is AuthMode.LOCAL


@pytest.mark.parametrize("mode", list(AuthMode))
async def test_choosing_a_mode_after_the_first_admin_is_closed_and_keeps_the_mode(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, mode: AuthMode
) -> None:
    """admin이 생긴 뒤 방식 선택은 닫힘 오류이고 방식은 그대로다.

    테스트 코드: SU-009
    """
    # given: 재직 admin이 있고 방식은 ad다
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_user(uow_factory, "boss", Role.ADMIN)

    # when: local 또는 ad를 고른다
    with pytest.raises(InvalidStateError) as caught:
        await auth.choose_mode.execute(mode)

    # then: 닫힘 문구의 invalid-state이고 방식은 ad 그대로다
    assert str(caught.value) == SETUP_CLOSED
    assert await _stored_mode(uow_factory) is AuthMode.AD
