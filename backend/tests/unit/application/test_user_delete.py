"""사용자 삭제 DeleteUser: 연결이 없으면 물리 삭제, 보호 규칙 (AC3·5, USER-4~7, T11·T15)."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.tokens import hash_token
from app.application.user.delete_user import DeleteOutcome
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from app.domain.user.errors import UserNotFoundError
from app.domain.user.value_objects import UserId
from tests.fakes.admin_stack import ADMIN_ACTOR, OTHER_ADMIN_ACTOR
from tests.support.admin_seed import active_logins, session_is_active
from tests.support.auth_seed import seed_user
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack


async def test_delete_user_without_links_removes_the_row_physically(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """연결이 없는 사용자를 삭제하면 행이 물리 삭제된다

    테스트 코드: US-057
    """
    # given: admin root와 연결 없는 kim
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)

    # when: kim을 삭제한다
    outcome = await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    # then: 결과가 deleted이고 kim 행이 없다
    assert outcome is DeleteOutcome.DELETED
    assert await active_logins(uow_factory) == ["root"]
    async with uow_factory() as uow:
        with pytest.raises(UserNotFoundError):
            await uow.users.get(target.id)


async def test_delete_outcome_values_are_stable_api_codes() -> None:
    """삭제 결과 값은 API 코드로 고정되어 있다"""
    # when: 결과 값 집합을 읽는다
    actual = {o.value for o in DeleteOutcome}
    # then: deleted·resigned 두 값이다
    assert actual == {"deleted", "resigned"}


async def test_delete_user_removes_every_session_row_of_that_user_only(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """삭제는 그 사용자의 세션 행만 모두 지운다

    테스트 코드: US-057
    """
    # given: kim의 세션 둘과 lee의 세션
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    lee = await seed_user(uow_factory, "lee", Role.SALES)
    first = (await auth.issue.execute(target.to_principal())).token
    second = (await auth.issue.execute(target.to_principal())).token
    other = (await auth.issue.execute(lee.to_principal())).token

    # when: kim을 삭제한다
    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    # then: kim의 세션 행은 없고 lee의 세션은 유지된다
    assert not await session_is_active(uow_factory, first)
    assert not await session_is_active(uow_factory, second)
    assert await session_is_active(uow_factory, other)
    async with (
        uow_factory() as uow
    ):  # 폐기가 아니라 행 삭제여야 FK 때문에 물리 삭제가 막히지 않는다
        assert await uow.sessions.get_by_token_hash(hash_token(first)) is None


async def test_deleting_a_user_blocks_the_session_immediately(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """삭제된 사용자의 기존 세션은 바로 인증에 실패한다

    테스트 코드: US-061
    """
    # given: kim의 세션
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    token = (await auth.issue.execute(target.to_principal())).token
    assert (await auth.authenticate.execute(token)).subject == "kim"

    # when: kim을 삭제한다
    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    # then: 같은 토큰의 인증이 실패한다
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(token)


async def test_delete_user_refuses_to_delete_oneself(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """admin은 자기 자신을 삭제할 수 없고 세션은 유지된다

    테스트 코드: US-065
    """
    # given: admin 둘, root의 세션
    me = await seed_user(uow_factory, "root", Role.ADMIN)
    await seed_user(uow_factory, "boss", Role.ADMIN)
    token = (await auth.issue.execute(me.to_principal())).token

    # when: root가 자기 자신을 삭제한다
    with pytest.raises(InvalidStateError, match="자기 자신"):
        await admin.delete_user.execute(user_id=me.id, actor=me.to_principal())

    # then: 자기 자신 오류이고 사용자·세션이 그대로다
    assert await active_logins(uow_factory) == ["boss", "root"]
    assert await session_is_active(uow_factory, token)  # 거부되면 세션 삭제도 일어나지 않는다


async def test_delete_user_refuses_the_last_active_admin(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """재직 admin이 하나뿐이면 그 admin을 삭제할 수 없다

    테스트 코드: US-066
    """
    # given: admin boss 하나와 그의 세션
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    await seed_user(uow_factory, "kim", Role.SALES)
    token = (await auth.issue.execute(boss.to_principal())).token

    # when: 다른 요청자가 boss를 삭제한다
    with pytest.raises(InvalidStateError, match="마지막 관리자"):
        await admin.delete_user.execute(user_id=boss.id, actor=OTHER_ADMIN_ACTOR)

    # then: 마지막 관리자 오류이고 사용자·세션이 그대로다
    assert await active_logins(uow_factory) == ["boss", "kim"]
    assert await session_is_active(uow_factory, token)


async def test_admin_count_drops_after_an_admin_is_deleted(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """admin이 삭제되면 재직 admin 수가 줄어 남은 admin도 삭제할 수 없다

    테스트 코드: US-066
    """
    # given: admin 둘 중 하나를 삭제함
    old = await seed_user(uow_factory, "old-admin", Role.ADMIN)
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    await admin.delete_user.execute(user_id=old.id, actor=OTHER_ADMIN_ACTOR)

    # when: 남은 admin을 삭제한다
    with pytest.raises(InvalidStateError, match="마지막 관리자"):
        await admin.delete_user.execute(user_id=boss.id, actor=OTHER_ADMIN_ACTOR)
    # then: 마지막 관리자 오류다


async def test_delete_user_allows_removing_an_admin_while_another_remains(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """재직 admin이 둘이면 다른 admin을 삭제할 수 있다

    테스트 코드: US-067
    """
    # given: admin root와 boss
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    other = await seed_user(uow_factory, "boss", Role.ADMIN)

    # when: root가 boss를 삭제한다
    await admin.delete_user.execute(user_id=other.id, actor=root.to_principal())

    # then: boss가 사라지고 root만 남는다
    assert await active_logins(uow_factory) == ["root"]


async def test_an_actor_without_a_users_row_can_delete_a_sales_user(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """요청자 행이 없어도 sales 사용자는 삭제할 수 있다"""
    # given: admin boss와 sales kim
    await seed_user(uow_factory, "boss", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)

    # when: 행 없는 요청자가 kim을 삭제한다
    outcome = await admin.delete_user.execute(user_id=target.id, actor=OTHER_ADMIN_ACTOR)

    # then: 결과가 deleted이고 boss만 남는다
    assert outcome is DeleteOutcome.DELETED
    assert await active_logins(uow_factory) == ["boss"]


async def test_delete_user_with_unknown_id_is_not_found(admin: AdminStack) -> None:
    """없는 id의 삭제는 없음 오류다

    테스트 코드: US-064
    """
    # when: 없는 id를 삭제한다
    with pytest.raises(UserNotFoundError):
        await admin.delete_user.execute(user_id=UserId(new_id()), actor=ADMIN_ACTOR)
    # then: 사용자 없음 오류다


async def test_physically_deleted_user_is_not_found_the_second_time(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """이미 물리 삭제된 사용자를 다시 삭제하면 없음 오류다

    테스트 코드: US-064
    """
    # given: 삭제된 kim
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    # when: kim을 다시 삭제한다
    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    # then: 사용자 없음 오류다
    with pytest.raises(UserNotFoundError):
        await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())


async def test_a_user_deleted_before_the_call_is_not_found(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """호출 전에 삭제된 사용자의 삭제는 없음 오류다

    테스트 코드: US-064
    """
    # given: 이미 물리 삭제된 사용자
    gone = await seed_user(uow_factory, "gone", Role.SALES, deleted=True)

    # when: 삭제한다
    with pytest.raises(UserNotFoundError):
        await admin.delete_user.execute(user_id=gone.id, actor=OTHER_ADMIN_ACTOR)
    # then: 사용자 없음 오류다
