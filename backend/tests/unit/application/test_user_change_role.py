"""R1 ChangeUserRole(AC1-1~1-8): 역할 변경, 세션 유지·다음 요청부터 새 역할, 보호 규칙."""

from typing import TYPE_CHECKING

import pytest

from app.application.user.change_user_role import ChangeUserRole
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from app.domain.user.errors import UserNotFoundError
from app.domain.user.value_objects import UserId
from tests.fakes.admin_stack import OTHER_ADMIN_ACTOR
from tests.support.admin_seed import session_is_active
from tests.support.auth_seed import seed_user
from tests.support.expect import raises_with
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FixedClock

SELF_CHANGE = "자기 자신의 역할은 바꿀 수 없습니다."
LAST_ADMIN = "마지막 관리자의 역할은 바꿀 수 없습니다."
RESIGNED = "이미 퇴사 처리된 사용자입니다"
DEV_ONLY = "개발 로그인 전용 사용자의 역할은 바꿀 수 없습니다."


@pytest.fixture
def change_role(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> ChangeUserRole:
    return ChangeUserRole(uow_factory, clock)


async def _role_of(uow_factory: UnitOfWorkFactory, user_id: UserId) -> Role:
    async with uow_factory() as uow:
        return (await uow.users.get(user_id)).role


async def test_change_user_role_saves_new_role(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    """admin이 다른 사용자의 역할을 바꾸면 새 역할이 저장된다

    테스트 코드: US-031
    """
    # given: admin root와 sales kim
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)

    # when: kim의 역할을 user로 바꾼다
    changed = await change_role.execute(
        user_id=target.id, role=Role.USER, actor=root.to_principal()
    )

    # then: 반환값과 저장된 역할이 user다
    assert changed.role is Role.USER
    assert await _role_of(uow_factory, target.id) is Role.USER


async def test_change_user_role_touches_updated_at_with_the_clock(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """역할을 바꾸면 수정 시각이 서버 시각이 된다

    테스트 코드: US-031
    """
    # given: admin root와 sales kim, 시계를 앞으로 돌림
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    clock.advance(600)

    # when: kim의 역할을 바꾼다
    changed = await change_role.execute(
        user_id=target.id, role=Role.ADMIN, actor=root.to_principal()
    )

    # then: 수정 시각이 현재 시각이다
    assert changed.updated_at == clock.now()
    async with uow_factory() as uow:
        assert (await uow.users.get(target.id)).updated_at == clock.now()


async def test_change_user_role_keeps_sessions_of_the_target(
    change_role: ChangeUserRole, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """역할을 바꿔도 대상의 세션은 유지된다

    테스트 코드: US-031
    """
    # given: kim의 세션 두 개
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    first = (await auth.issue.execute(target.to_principal())).token
    second = (await auth.issue.execute(target.to_principal())).token

    # when: kim의 역할을 바꾼다
    await change_role.execute(user_id=target.id, role=Role.USER, actor=root.to_principal())

    # then: 두 세션 모두 활성이다
    assert await session_is_active(uow_factory, first)
    assert await session_is_active(uow_factory, second)


async def test_authenticate_returns_new_role_after_change(
    change_role: ChangeUserRole, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """바뀐 역할은 대상의 다음 요청부터 적용된다

    테스트 코드: US-032
    """
    # given: sales kim의 세션
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    token = (await auth.issue.execute(target.to_principal())).token
    assert (await auth.authenticate.execute(token)).role is Role.SALES

    # when: 역할을 user로 바꾼다
    await change_role.execute(user_id=target.id, role=Role.USER, actor=root.to_principal())

    # then: 같은 토큰의 인증 결과 역할이 user다
    assert (await auth.authenticate.execute(token)).role is Role.USER


async def test_change_user_role_refuses_oneself(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    """자기 자신의 역할은 바꿀 수 없다

    테스트 코드: US-034
    """
    # given: admin 둘
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    await seed_user(uow_factory, "boss", Role.ADMIN)

    # when: root가 자기 역할을 바꾼다
    with raises_with(InvalidStateError, SELF_CHANGE):
        await change_role.execute(user_id=root.id, role=Role.USER, actor=root.to_principal())

    # then: 자기 자신 오류이고 역할은 admin 그대로다
    assert await _role_of(uow_factory, root.id) is Role.ADMIN


async def test_change_user_role_refuses_demoting_the_last_admin(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    """재직 admin이 하나뿐이면 강등할 수 없다

    테스트 코드: US-035
    """
    # given: admin boss 하나
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    await seed_user(uow_factory, "kim", Role.SALES)

    # when: 다른 요청자가 boss를 sales로 바꾼다
    with raises_with(InvalidStateError, LAST_ADMIN):
        await change_role.execute(user_id=boss.id, role=Role.SALES, actor=OTHER_ADMIN_ACTOR)

    # then: 마지막 관리자 오류이고 역할은 그대로다
    assert await _role_of(uow_factory, boss.id) is Role.ADMIN


async def test_change_user_role_allows_demoting_an_admin_while_another_remains(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    """재직 admin이 둘이면 다른 admin을 강등할 수 있다

    테스트 코드: US-033
    """
    # given: admin root와 boss
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    other = await seed_user(uow_factory, "boss", Role.ADMIN)

    # when: root가 boss를 sales로 바꾼다
    await change_role.execute(user_id=other.id, role=Role.SALES, actor=root.to_principal())

    # then: boss의 역할이 sales다
    assert await _role_of(uow_factory, other.id) is Role.SALES


async def test_change_user_role_counts_only_active_admins(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    """퇴사한 admin은 재직 admin 수에 세지 않는다

    테스트 코드: US-035
    """
    # given: 재직 admin boss와 퇴사한 admin
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    await seed_user(uow_factory, "old-admin", Role.ADMIN, resigned=True)

    # when: 다른 요청자가 boss를 강등한다
    with raises_with(InvalidStateError, LAST_ADMIN):
        await change_role.execute(user_id=boss.id, role=Role.USER, actor=OTHER_ADMIN_ACTOR)
    # then: 마지막 관리자 오류다


async def test_change_user_role_refuses_resigned_user(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    """퇴사자의 역할은 바꿀 수 없다

    테스트 코드: US-036
    """
    # given: 퇴사한 sales
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    gone = await seed_user(uow_factory, "gone", Role.SALES, resigned=True)

    # when: 역할을 바꾼다
    with raises_with(InvalidStateError, RESIGNED):
        await change_role.execute(user_id=gone.id, role=Role.USER, actor=root.to_principal())

    # then: 퇴사 처리 오류이고 역할은 그대로다
    assert await _role_of(uow_factory, gone.id) is Role.SALES


async def test_change_user_role_with_same_role_does_not_write(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """지금과 같은 역할을 보내면 저장하지 않고 그대로 돌려준다

    테스트 코드: US-037
    """
    # given: sales kim, 시계를 앞으로 돌림
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    clock.advance(600)

    # when: 같은 sales로 바꾼다
    result = await change_role.execute(
        user_id=target.id, role=Role.SALES, actor=root.to_principal()
    )

    # then: 수정 시각이 바뀌지 않는다
    assert result.role is Role.SALES
    assert result.updated_at == target.updated_at
    async with uow_factory() as active:
        assert (await active.users.get(target.id)).updated_at == target.updated_at


async def test_change_user_role_with_unknown_id_is_not_found(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    """없는 사용자의 역할 변경은 없음 오류다

    테스트 코드: US-038
    """
    # given: admin root
    root = await seed_user(uow_factory, "root", Role.ADMIN)

    # when: 없는 id의 역할을 바꾼다
    with pytest.raises(UserNotFoundError):
        await change_role.execute(
            user_id=UserId(new_id()), role=Role.USER, actor=root.to_principal()
        )
    # then: 사용자 없음 오류다


async def test_change_user_role_leaves_other_users_unchanged(
    change_role: ChangeUserRole, uow_factory: UnitOfWorkFactory
) -> None:
    """역할 변경은 다른 사용자에게 영향이 없다"""
    # given: admin root, sales kim과 lee
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    lee = await seed_user(uow_factory, "lee", Role.SALES)

    # when: kim의 역할을 바꾼다
    await change_role.execute(user_id=target.id, role=Role.USER, actor=root.to_principal())

    # then: lee와 root의 역할은 그대로다
    assert await _role_of(uow_factory, lee.id) is Role.SALES
    assert await _role_of(uow_factory, root.id) is Role.ADMIN
