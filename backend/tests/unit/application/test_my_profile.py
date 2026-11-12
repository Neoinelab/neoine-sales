"""GetMyProfile·UpdateMyProfile: 로그인한 사용자 자신의 정보 (ME-R3~R8).

local: 이름(비울 수 없음)·이메일·전화와 비밀번호 변경. ad: 전화만.
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
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


async def _kim(uow_factory: UnitOfWorkFactory, role: Role = Role.SALES) -> User:
    return await seed_local_user(
        uow_factory, "kim", "kim-password-1", role, display_name="김영업", email="kim@corp.test"
    )


async def test_my_profile_editable_flags_in_local_mode(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """local 모드에서는 이름·이메일·비밀번호를 모두 고칠 수 있다.

    테스트 코드: ME-001
    """
    # given: local 모드이고 kim(이름 "김영업")이 있다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await _kim(uow_factory)

    # when: 내 정보를 조회한다
    profile = await admin.get_my_profile.execute(kim.to_principal())

    # then: 모드는 local이고 수정 가능 표시가 모두 true다
    assert profile.mode is AuthMode.LOCAL
    assert (profile.can_edit_name_email, profile.can_change_password) == (True, True)
    assert (profile.user.login_id.value, profile.user.display_name) == ("kim", "김영업")


async def test_my_profile_editable_flags_in_ad_mode(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """AD 모드에서는 이름·이메일·비밀번호를 고칠 수 없다.

    테스트 코드: ME-002
    """
    # given: AD 모드이고 kim이 있다
    await seed_auth_mode(uow_factory, AuthMode.AD)
    kim = await _kim(uow_factory)

    # when: 내 정보를 조회한다
    profile = await admin.get_my_profile.execute(kim.to_principal())

    # then: 모드는 ad이고 이름·이메일·비밀번호 수정은 불가다
    assert profile.mode is AuthMode.AD
    assert (profile.can_edit_name_email, profile.can_change_password) == (False, False)


async def test_my_profile_without_a_mode_row_in_a_legacy_system_is_ad(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """인증 방식 행이 없는 기존 시스템은 AD 모드로 본다.

    테스트 코드: ME-003
    """
    # given: 인증 방식 행이 없고 재직 admin이 있는 시스템의 kim이다
    kim = await _kim(uow_factory)
    boss = await seed_local_user(uow_factory, "boss", "boss-password-1", Role.ADMIN)

    # when: 내 정보를 조회한다
    profile = await admin.get_my_profile.execute(kim.to_principal())

    # then: 모드는 ad이고 이름·이메일·비밀번호 수정은 불가다
    assert boss.is_active
    assert profile.mode is AuthMode.AD
    assert (profile.can_edit_name_email, profile.can_change_password) == (False, False)


async def test_my_profile_shows_phone_and_email_or_none(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """이메일이 없으면 None, 전화는 저장된 값으로 보인다.

    테스트 코드: ME-001
    """
    # given: local 모드이고 이메일 없이 전화만 있는 lee가 있다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    lee = await seed_local_user(uow_factory, "lee", "lee-password-1", phone="02-123-4567")

    # when: 내 정보를 조회한다
    profile = await admin.get_my_profile.execute(lee.to_principal())

    # then: 이메일은 None, 전화는 02-123-4567이다
    assert (profile.user.email, profile.user.phone) == (None, "02-123-4567")


# ---- UpdateMyProfile ----


async def test_update_my_profile_changes_own_row_only(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """수정은 자기 행만 바꾸고 아이디·역할·다른 사용자는 그대로다.

    테스트 코드: ME-007
    """
    # given: local 모드이고 kim(sales)과 lee(이름 "이영업", 전화 없음)가 있다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await _kim(uow_factory)
    lee = await seed_local_user(uow_factory, "lee", "lee-password-1", display_name="이영업")

    # when: kim이 이름 "김새이름"·전화 010-9999-8888로 고친다
    result = await admin.update_my_profile.execute(
        actor=kim.to_principal(),
        changes=ProfileChanges(display_name="김새이름", phone="010-9999-8888"),
    )

    # then: kim만 바뀌고 lee는 그대로이며 kim의 아이디·역할도 그대로다
    assert (result.user.display_name, result.user.phone) == ("김새이름", "010-9999-8888")
    assert result.can_edit_name_email is True
    stored_lee = await uow.users.get(lee.id)
    assert (stored_lee.display_name, stored_lee.phone) == ("이영업", None)
    stored_kim = await uow.users.get(kim.id)
    assert (stored_kim.login_id.value, stored_kim.role) == ("kim", Role.SALES)


async def test_update_my_profile_name_is_visible_to_the_next_authentication(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """고친 이름은 다음 인증(/auth/me)부터 보인다.

    테스트 코드: ME-006
    """
    # given: local 모드이고 kim이 세션을 발급받았다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await _kim(uow_factory)
    issued = await auth.issue.execute(kim.to_principal())

    # when: 이름을 "김새이름"으로 고친다
    await admin.update_my_profile.execute(
        actor=kim.to_principal(), changes=ProfileChanges(display_name="김새이름")
    )

    # then: 그 세션을 인증하면 이름이 "김새이름"이다
    assert (await auth.authenticate.execute(issued.token)).name == "김새이름"


async def test_update_my_profile_blank_name_in_local_mode_is_invalid_value(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """local 모드에서 이름을 공백만으로 비우면 InvalidValueError이고 이름은 그대로다.

    테스트 코드: ME-011
    """
    # given: local 모드이고 kim(이름 "김영업")이 있다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await _kim(uow_factory)

    # when: 이름을 " "로 고친다
    with pytest.raises(InvalidValueError):
        await admin.update_my_profile.execute(
            actor=kim.to_principal(), changes=ProfileChanges(display_name=" ")
        )

    # then: 저장된 이름은 "김영업"이다
    assert (await uow.users.get(kim.id)).display_name == "김영업"


async def test_update_my_profile_invalid_email_is_invalid_value(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """형식이 틀린 이메일은 InvalidValueError이고 값이 바뀌지 않는다.

    테스트 코드: ME-010
    """
    # given: local 모드이고 kim(이메일 kim@corp.test)이 있다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await _kim(uow_factory)

    # when: 이메일을 "abc"로 고친다
    with pytest.raises(InvalidValueError):
        await admin.update_my_profile.execute(
            actor=kim.to_principal(), changes=ProfileChanges(email="abc")
        )

    # then: 저장된 이메일은 그대로다
    assert (await uow.users.get(kim.id)).email == "kim@corp.test"


async def test_update_my_profile_clears_email_and_phone_with_none(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """None을 보내면 이메일·전화를 비운다.

    테스트 코드: ME-008
    """
    # given: local 모드이고 이메일·전화가 있는 kim이 있다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await seed_local_user(
        uow_factory,
        "kim",
        "kim-password-1",
        display_name="김영업",
        email="k@c.co",
        phone="02-123-4567",
    )

    # when: 이메일·전화를 None으로 고친다
    result = await admin.update_my_profile.execute(
        actor=kim.to_principal(), changes=ProfileChanges(email=None, phone=None)
    )

    # then: 이메일·전화가 None이고 이름은 그대로다
    assert (result.user.email, result.user.phone) == (None, None)
    assert result.user.display_name == "김영업"


async def test_update_my_profile_with_no_change_or_same_values_keeps_updated_at(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    """빈 변경이나 같은 값은 저장하지 않아 updated_at이 그대로다.

    테스트 코드: ME-009
    """
    # given: local 모드이고 전화가 있는 kim이 있고 시계가 흘렀다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await seed_local_user(uow_factory, "kim", "kim-password-1", phone="02-123-4567")
    before = (await uow.users.get(kim.id)).updated_at
    clock.advance(3600)

    # when: 빈 변경을 보내고, 따로 지금과 같은 전화만 보낸다
    empty = await admin.update_my_profile.execute(
        actor=kim.to_principal(), changes=ProfileChanges()
    )
    same = await admin.update_my_profile.execute(
        actor=kim.to_principal(), changes=ProfileChanges(phone="02-123-4567")
    )

    # then: 둘 다 현재 값을 주고 저장된 updated_at은 바뀌지 않는다
    assert (empty.user.phone, same.user.phone) == ("02-123-4567", "02-123-4567")
    assert (await uow.users.get(kim.id)).updated_at == before


async def test_update_my_profile_normalizes_values_and_accepts_the_boundaries(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """이름·이메일·전화는 정규화해 저장하고 경계값을 받아들인다.

    테스트 코드: ME-016
    """
    # given: local 모드이고 kim이 있다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    kim = await _kim(uow_factory)

    # when: 공백·대문자가 섞인 값을 고치고, 따로 200자 이름·공백뿐인 이메일·7자리 전화로 고친다
    normalized = await admin.update_my_profile.execute(
        actor=kim.to_principal(),
        changes=ProfileChanges(
            display_name="  김새이름  ", email="  Kim@Corp.TEST ", phone=" 02-123-4567 "
        ),
    )
    boundary = await admin.update_my_profile.execute(
        actor=kim.to_principal(),
        changes=ProfileChanges(display_name="가" * 200, email="   ", phone="1234567"),
    )

    # then: 앞은 다듬어진 값, 뒤는 200자 이름 그대로·이메일 None·전화 1234567이다
    assert (normalized.user.display_name, normalized.user.email, normalized.user.phone) == (
        "김새이름",
        "kim@corp.test",
        "02-123-4567",
    )
    assert (boundary.user.display_name, boundary.user.email, boundary.user.phone) == (
        "가" * 200,
        None,
        "1234567",
    )


@pytest.mark.parametrize(
    "changes",
    [
        ProfileChanges(display_name="새 이름"),
        ProfileChanges(email="a@b.co"),
        ProfileChanges(email="abc"),
        ProfileChanges(email=None),
    ],
)
async def test_update_my_profile_name_or_email_in_ad_mode_is_invalid_state(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, changes: ProfileChanges
) -> None:
    """AD 모드에서 이름·이메일 키가 있으면 값 검증 전에 InvalidStateError다.

    테스트 코드: ME-013
    """
    # given: AD 모드이고 kim이 있다
    await seed_auth_mode(uow_factory, AuthMode.AD)
    kim = await _kim(uow_factory)

    # when·then: 이름 또는 이메일(틀린 형식·None 포함)을 고친다 → InvalidStateError다
    with pytest.raises(InvalidStateError):
        await admin.update_my_profile.execute(actor=kim.to_principal(), changes=changes)


async def test_update_my_profile_phone_only_in_ad_mode(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """AD 모드에서도 전화는 고칠 수 있다.

    테스트 코드: ME-014
    """
    # given: AD 모드이고 kim이 있다
    await seed_auth_mode(uow_factory, AuthMode.AD)
    kim = await _kim(uow_factory)

    # when: 전화만 고친다
    result = await admin.update_my_profile.execute(
        actor=kim.to_principal(), changes=ProfileChanges(phone="010-1111-2222")
    )

    # then: 전화가 바뀌고 이름·이메일은 수정 불가 표시다
    assert result.user.phone == "010-1111-2222"
    assert result.can_edit_name_email is False


async def test_update_my_profile_of_a_resigned_actor_is_rejected(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """퇴사 처리된 행의 정보 수정은 InvalidStateError이고 값이 바뀌지 않는다.

    테스트 코드: ME-015
    """
    # given: local 모드이고 퇴사 처리된 사용자 gone의 로그인 주체가 있다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    gone = await seed_local_user(uow_factory, "gone", "gone-password-1", resigned=True)

    # when: gone이 전화 02-123-4567로 고친다
    with pytest.raises(InvalidStateError):
        await admin.update_my_profile.execute(
            actor=gone.to_principal(), changes=ProfileChanges(phone="02-123-4567")
        )

    # then: 저장된 전화는 없는 그대로다
    assert (await uow.users.get(gone.id)).phone is None
