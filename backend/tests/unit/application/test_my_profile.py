"""GetMyProfile·UpdateMyProfile: 로그인한 사용자 자신의 정보 (AC-9·AC-10).

local: 이름(비울 수 없음)·이메일·전화와 비밀번호 변경. ad: 전화만. dev 사용자는 비밀번호 변경 불가.
요청자 자신의 행만 바꾸고, 고친 이름은 다음 인증 때 바로 보인다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.user.profile import ProfileChanges
from tests.support.auth_seed import seed_auth_mode, seed_local_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.entities import User
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork


async def _kim(uow_factory: UnitOfWorkFactory, role: Role = Role.SALES) -> User:
    return await seed_local_user(
        uow_factory, "kim", "kim-password-1", role, display_name="김영업", email="kim@corp.test"
    )


async def test_my_profile_editable_flags_in_local_mode(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await _kim(uow_factory)

    profile = await admin.get_my_profile.execute(kim.to_principal())

    assert profile.mode is AuthMode.LOCAL
    assert (profile.can_edit_name_email, profile.can_change_password) == (True, True)
    assert (profile.user.login_id.value, profile.user.display_name) == ("kim", "김영업")


async def test_my_profile_editable_flags_in_ad_mode(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.AD)
    kim = await _kim(uow_factory)

    profile = await admin.get_my_profile.execute(kim.to_principal())

    assert profile.mode is AuthMode.AD
    assert (profile.can_edit_name_email, profile.can_change_password) == (False, False)


async def test_my_profile_without_a_mode_row_in_a_legacy_system_is_ad(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    kim = await _kim(uow_factory)
    boss = await seed_local_user(uow_factory, "boss", "boss-password-1", Role.ADMIN)

    profile = await admin.get_my_profile.execute(kim.to_principal())

    assert boss.is_active
    assert profile.mode is AuthMode.AD
    assert (profile.can_edit_name_email, profile.can_change_password) == (False, False)


@pytest.mark.parametrize("login_id", ["dev-admin", "dev-sales", "dev-user"])
async def test_my_profile_for_dev_user_disallows_password(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, login_id: str
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    dev = await seed_local_user(uow_factory, login_id, "unused-pass-1", with_hash=False)

    profile = await admin.get_my_profile.execute(dev.to_principal())

    assert (profile.can_edit_name_email, profile.can_change_password) == (True, False)


async def test_my_profile_shows_phone_and_email_or_none(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    lee = await seed_local_user(uow_factory, "lee", "lee-password-1", phone="02-123-4567")

    profile = await admin.get_my_profile.execute(lee.to_principal())

    assert (profile.user.email, profile.user.phone) == (None, "02-123-4567")


# ---- UpdateMyProfile ----


async def test_update_my_profile_changes_own_row_only(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await _kim(uow_factory)
    lee = await seed_local_user(uow_factory, "lee", "lee-password-1", display_name="이영업")

    result = await admin.update_my_profile.execute(
        actor=kim.to_principal(),
        changes=ProfileChanges(display_name="김새이름", phone="010-9999-8888"),
    )

    assert (result.user.display_name, result.user.phone) == ("김새이름", "010-9999-8888")
    assert result.can_edit_name_email is True
    stored_lee = await uow.users.get(lee.id)
    assert (stored_lee.display_name, stored_lee.phone) == ("이영업", None)
    stored_kim = await uow.users.get(kim.id)
    assert (stored_kim.login_id.value, stored_kim.role) == ("kim", Role.SALES)


async def test_update_my_profile_name_is_visible_to_the_next_authentication(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await _kim(uow_factory)
    issued = await auth.issue.execute(kim.to_principal())

    await admin.update_my_profile.execute(
        actor=kim.to_principal(), changes=ProfileChanges(display_name="김새이름")
    )

    assert (await auth.authenticate.execute(issued.token)).name == "김새이름"


async def test_update_my_profile_blank_name_in_local_mode_is_invalid_value(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await _kim(uow_factory)

    with pytest.raises(InvalidValueError):
        await admin.update_my_profile.execute(
            actor=kim.to_principal(), changes=ProfileChanges(display_name=" ")
        )

    assert (await uow.users.get(kim.id)).display_name == "김영업"


async def test_update_my_profile_invalid_email_is_invalid_value(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await _kim(uow_factory)

    with pytest.raises(InvalidValueError):
        await admin.update_my_profile.execute(
            actor=kim.to_principal(), changes=ProfileChanges(email="abc")
        )


async def test_update_my_profile_clears_email_and_phone_with_none(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await seed_local_user(
        uow_factory,
        "kim",
        "kim-password-1",
        display_name="김영업",
        email="k@c.co",
        phone="02-123-4567",
    )

    result = await admin.update_my_profile.execute(
        actor=kim.to_principal(), changes=ProfileChanges(email=None, phone=None)
    )

    assert (result.user.email, result.user.phone) == (None, None)


@pytest.mark.parametrize(
    "changes", [ProfileChanges(display_name="새 이름"), ProfileChanges(email="a@b.co")]
)
async def test_update_my_profile_name_or_email_in_ad_mode_is_invalid_state(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, changes: ProfileChanges
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.AD)
    kim = await _kim(uow_factory)

    with pytest.raises(InvalidStateError):
        await admin.update_my_profile.execute(actor=kim.to_principal(), changes=changes)


async def test_update_my_profile_phone_only_in_ad_mode(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.AD)
    kim = await _kim(uow_factory)

    result = await admin.update_my_profile.execute(
        actor=kim.to_principal(), changes=ProfileChanges(phone="010-1111-2222")
    )

    assert result.user.phone == "010-1111-2222"
    assert result.can_edit_name_email is False


async def test_update_my_profile_of_a_resigned_actor_is_rejected(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    gone = await seed_local_user(uow_factory, "gone", "gone-password-1", resigned=True)

    with pytest.raises(InvalidStateError):
        await admin.update_my_profile.execute(
            actor=gone.to_principal(), changes=ProfileChanges(phone="02-123-4567")
        )
