"""UpdateUserProfile: admin이 다른 사용자의 이름·이메일·전화를 고친다.

local은 셋 다, ad(방식 행 없는 기존 시스템 포함)는 전화만. 퇴사자는 InvalidStateError.
보내지 않은 값(UNSET)은 그대로 두고 None은 비운다. 아이디·역할은 바꾸지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.user.errors import UserNotFoundError
from app.domain.user.profile import ProfileChanges
from tests.support.auth_seed import seed_auth_mode, seed_local_user
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal
    from app.domain.user.entities import User
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.unit_of_work import FakeUnitOfWork


@pytest.fixture
async def boss(uow_factory: UnitOfWorkFactory) -> Principal:
    user = await seed_local_user(uow_factory, "boss", "boss-password-1", Role.ADMIN)
    return user.to_principal()


@pytest.fixture
async def local_mode(uow_factory: UnitOfWorkFactory) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)


async def _kim(uow_factory: UnitOfWorkFactory) -> User:
    return await seed_local_user(
        uow_factory,
        "kim",
        "kim-password-1",
        display_name="김영업",
        email="kim@corp.test",
        phone="010-1234-5678",
    )


@pytest.mark.usefixtures("local_mode")
async def test_admin_updates_profile_in_local_mode(
    admin: AdminStack, boss: Principal, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """local 모드에서 admin이 이름·이메일·전화를 고치면 반영되고 아이디·역할은 그대로다

    테스트 코드: US-040
    """
    # given: local 모드, 프로필이 있는 kim
    kim = await _kim(uow_factory)

    # when: 이름·이메일·전화를 고친다
    updated = await admin.update_profile.execute(
        user_id=kim.id,
        changes=ProfileChanges(display_name="이영업", email="Lee@Corp.test", phone="02-123-4567"),
        actor=boss,
    )

    # then: 정규화된 새 값이 저장되고 아이디·역할은 그대로다
    assert (updated.display_name, updated.email, updated.phone) == (
        "이영업",
        "lee@corp.test",
        "02-123-4567",
    )
    stored = await uow.users.get(kim.id)
    assert (stored.display_name, stored.email, stored.phone) == (
        "이영업",
        "lee@corp.test",
        "02-123-4567",
    )
    assert (stored.login_id.value, stored.role) == ("kim", Role.SALES)


@pytest.mark.usefixtures("local_mode")
async def test_unset_fields_are_kept_and_none_clears(
    admin: AdminStack, boss: Principal, uow_factory: UnitOfWorkFactory
) -> None:
    """보낸 칸만 바뀌고 None은 그 칸을 비운다

    테스트 코드: US-041
    """
    # given: local 모드, 프로필이 있는 kim
    kim = await _kim(uow_factory)

    # when: 이메일만 None으로 보낸다
    updated = await admin.update_profile.execute(
        user_id=kim.id, changes=ProfileChanges(email=None), actor=boss
    )

    # then: 이메일만 비고 이름·전화는 그대로다
    assert (updated.display_name, updated.email, updated.phone) == (
        "김영업",
        None,
        "010-1234-5678",
    )


@pytest.mark.usefixtures("local_mode")
async def test_update_without_effective_changes_does_not_commit(
    admin: AdminStack, boss: Principal, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """바뀐 값이 없으면 저장하지 않는다

    테스트 코드: US-042
    """
    # given: local 모드, 이름이 김영업인 kim
    kim = await _kim(uow_factory)
    uow.commits = 0

    # when: 같은 이름을 보낸다
    await admin.update_profile.execute(
        user_id=kim.id, changes=ProfileChanges(display_name="김영업"), actor=boss
    )

    # then: 커밋이 일어나지 않는다
    assert uow.commits == 0


@pytest.mark.usefixtures("local_mode")
@pytest.mark.parametrize("name", [None, "", "  "])
async def test_blank_name_in_local_mode_is_invalid_value(
    admin: AdminStack,
    boss: Principal,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    name: str | None,
) -> None:
    """local 모드에서 이름을 비우면 입력 오류이고 이름은 그대로다

    테스트 코드: US-043
    """
    # given: local 모드, kim
    kim = await _kim(uow_factory)

    # when: 이름을 비워 보낸다
    with pytest.raises(InvalidValueError):
        await admin.update_profile.execute(
            user_id=kim.id, changes=ProfileChanges(display_name=name), actor=boss
        )

    # then: 입력 오류이고 이름은 김영업 그대로다
    assert (await uow.users.get(kim.id)).display_name == "김영업"


@pytest.mark.usefixtures("local_mode")
@pytest.mark.parametrize("changes", [ProfileChanges(email="abc"), ProfileChanges(phone="12")])
async def test_invalid_email_or_phone_is_invalid_value(
    admin: AdminStack,
    boss: Principal,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    changes: ProfileChanges,
) -> None:
    """형식이 틀린 이메일·전화로 고치면 입력 오류이고 아무 칸도 바뀌지 않는다

    테스트 코드: US-044
    """
    # given: local 모드, 프로필이 있는 kim
    kim = await _kim(uow_factory)

    # when: 잘못된 이메일 또는 전화를 보낸다
    with pytest.raises(InvalidValueError):
        await admin.update_profile.execute(user_id=kim.id, changes=changes, actor=boss)

    # then: 입력 오류이고 이름·이메일·전화가 그대로다
    stored = await uow.users.get(kim.id)
    assert (stored.display_name, stored.email, stored.phone) == (
        "김영업",
        "kim@corp.test",
        "010-1234-5678",
    )


@pytest.mark.parametrize("mode", [AuthMode.AD, None])
@pytest.mark.parametrize(
    "changes", [ProfileChanges(display_name="새 이름"), ProfileChanges(email="a@b.co")]
)
async def test_admin_name_or_email_edit_in_ad_mode_is_invalid_state(  # noqa: PLR0913, PLR0917
    admin: AdminStack,
    boss: Principal,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    mode: AuthMode | None,
    changes: ProfileChanges,
) -> None:
    """AD 모드에서 이름·이메일 수정은 상태 오류이고 값은 그대로다

    테스트 코드: US-045
    """
    # given: AD 모드(방식 행 없음 포함), kim
    kim = await _kim(uow_factory)
    if mode is not None:
        await seed_auth_mode(uow_factory, mode)
    else:
        uow.auth_settings._items.clear()

    # when: 이름 또는 이메일을 보낸다
    with pytest.raises(InvalidStateError):
        await admin.update_profile.execute(user_id=kim.id, changes=changes, actor=boss)

    # then: 상태 오류이고 이름·이메일이 그대로다
    stored = await uow.users.get(kim.id)
    assert (stored.display_name, stored.email) == ("김영업", "kim@corp.test")


async def test_admin_edits_only_the_phone_in_ad_mode(
    admin: AdminStack, boss: Principal, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """AD 모드에서도 전화는 고칠 수 있다

    테스트 코드: US-045
    """
    # given: AD 모드, kim
    kim = await _kim(uow_factory)
    await seed_auth_mode(uow_factory, AuthMode.AD)

    # when: 전화만 보낸다
    updated = await admin.update_profile.execute(
        user_id=kim.id, changes=ProfileChanges(phone="02-123-4567"), actor=boss
    )

    # then: 전화가 바뀌고 이름은 그대로다
    assert updated.phone == "02-123-4567"
    assert (await uow.users.get(kim.id)).display_name == "김영업"


@pytest.mark.usefixtures("local_mode")
async def test_update_of_a_resigned_user_is_invalid_state(
    admin: AdminStack, boss: Principal, uow_factory: UnitOfWorkFactory
) -> None:
    """퇴사자의 정보는 고칠 수 없다

    테스트 코드: US-046
    """
    # given: local 모드, 퇴사한 사용자
    gone = await seed_local_user(uow_factory, "gone", "gone-password-1", resigned=True)

    # when: 전화를 고친다
    with pytest.raises(InvalidStateError):
        await admin.update_profile.execute(
            user_id=gone.id, changes=ProfileChanges(phone="02-123-4567"), actor=boss
        )
    # then: 상태 오류다


@pytest.mark.usefixtures("local_mode")
async def test_update_of_an_unknown_user_is_not_found(admin: AdminStack, boss: Principal) -> None:
    """없는 사용자의 정보 수정은 없음 오류다

    테스트 코드: US-047
    """
    # when: 없는 id를 고친다 (전제: local 모드)
    with pytest.raises(UserNotFoundError):
        await admin.update_profile.execute(
            user_id=uid("ghost"), changes=ProfileChanges(phone="02-123-4567"), actor=boss
        )
    # then: 사용자 없음 오류다
