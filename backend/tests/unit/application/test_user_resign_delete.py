"""사용자 삭제의 퇴사 분기: 연결이 있으면 행을 남기고 퇴사 처리 (AC3·4·5, T11·T14·T19)."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.tokens import hash_token
from app.application.ports.deal_repository import DealQuery
from app.application.user.delete_user import DeleteOutcome
from app.domain.auth.credentials import Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from app.domain.user.errors import UserInUseError
from app.domain.user.value_objects import UserStatusFilter
from tests.factories import NOW
from tests.fakes.admin_stack import OTHER_ADMIN_ACTOR
from tests.support.admin_seed import session_is_active
from tests.support.auth_seed import seed_auth_mode, seed_local_user, seed_user
from tests.support.user_links import LINK_KINDS, link_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork


@pytest.mark.parametrize("kind", LINK_KINDS)
async def test_delete_user_with_any_reference_resigns_instead_of_deleting(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, kind: str
) -> None:
    """연결이 하나라도 있으면 삭제는 퇴사 처리가 된다

    테스트 코드: US-058
    """
    # given: 연결 종류 하나가 있는 kim
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, target, kind)

    # when: kim을 삭제한다
    outcome = await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    # then: 결과가 resigned이고 행은 퇴사 시각과 함께 남는다
    assert outcome is DeleteOutcome.RESIGNED
    async with uow_factory() as uow:
        kept = await uow.users.get(target.id)
    assert kept.deleted_at == NOW
    assert kept.login_id.value == "kim"


@pytest.mark.parametrize("kind", LINK_KINDS)
async def test_resigning_still_deletes_the_users_session_rows(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory, kind: str
) -> None:
    """퇴사 처리도 대상의 세션 행을 지운다

    테스트 코드: US-058
    """
    # given: 연결과 세션이 있는 kim
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, target, kind)
    token = (await auth.issue.execute(target.to_principal())).token

    # when: kim을 삭제한다
    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    # then: 세션이 끝나고 세션 행이 없다
    assert not await session_is_active(uow_factory, token)
    async with uow_factory() as uow:
        assert await uow.sessions.get_by_token_hash(hash_token(token)) is None


def test_registering_another_user_is_not_one_of_the_sixteen_links() -> None:
    """연결 종류는 16종이고 사용자 등록자는 그 안에 없다

    테스트 코드: US-058
    """
    # when: 테스트 지원 코드의 연결 종류 목록을 본다
    # then: 16종이며 사용자 등록자(created_user)는 없다
    assert len(LINK_KINDS) == 16
    assert "created_user" not in LINK_KINDS


async def test_an_admin_who_only_registered_another_user_is_deleted_physically(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """다른 사용자를 등록했을 뿐인 admin은 물리 삭제되고 그가 등록한 사용자는 재직 그대로다

    테스트 코드: US-112
    """
    # given: boss가 kim을 등록했고 boss에게 다른 연결은 없다
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    kim = await admin.register_user.execute(
        login_id="kim", role=Role.SALES, actor=boss.to_principal()
    )

    # when: root가 boss를 삭제한다
    outcome = await admin.delete_user.execute(user_id=boss.id, actor=root.to_principal())

    # then: boss는 deleted로 행이 없고 어떤 목록에도 없으며 kim은 재직 그대로다
    assert outcome is DeleteOutcome.DELETED
    logins = {u.login_id.value for u in await admin.list_users.execute(status=UserStatusFilter.ALL)}
    assert logins == {"root", "kim"}
    async with uow_factory() as uow:
        assert (await uow.users.get(kim.id)).is_active


async def test_resigned_user_keeps_the_references_that_pointed_to_him(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """퇴사 처리해도 그를 가리키던 참조는 남고 퇴사로 표시된다

    테스트 코드: US-058
    """
    # given: 소유 Deal이 있는 kim
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, target, "deal_owner")

    # when: kim을 삭제한다
    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    # then: Deal의 Owner 참조가 퇴사 표시를 가진다
    async with uow_factory() as uow:
        (item,) = await uow.deals.search(DealQuery())
        deal = item.deal
        refs = await uow.users.get_refs([deal.details.owner_user_id])
    assert refs[target.id].resigned is True
    assert refs[target.id].label.endswith("(퇴사)")


async def test_resigned_user_cannot_be_deleted_again(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """이미 퇴사한 사용자를 다시 삭제하면 상태 오류다

    테스트 코드: US-063
    """
    # given: 퇴사 처리된 kim
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, target, "deal_owner")
    # when: kim을 다시 삭제한다
    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    # then: 이미 퇴사 오류이고 첫 퇴사 시각이 그대로다
    with pytest.raises(InvalidStateError, match="이미 퇴사"):
        await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    async with uow_factory() as uow:
        assert (await uow.users.get(target.id)).deleted_at == NOW  # 첫 퇴사 시각 그대로


async def test_resigned_user_cannot_log_in_even_with_a_surviving_session(
    auth: AuthStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """세션 행이 남아도 퇴사자는 인증에 실패한다

    테스트 코드: US-061
    """
    # given: 세션이 남은 채 퇴사된 kim
    target = await seed_user(uow_factory, "kim", Role.SALES)
    token = (await auth.issue.execute(target.to_principal())).token
    async with uow_factory() as active:
        user = await active.users.get(target.id)
        user.resign(NOW)
        await active.users.update(user)
        await active.commit()

    # when: 그 토큰으로 인증한다
    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(token)
    # then: 인증 오류다


async def test_last_admin_protection_also_applies_to_the_resign_branch(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """마지막 admin 보호는 퇴사 분기에도 적용된다

    테스트 코드: US-066
    """
    # given: 연결이 있는 마지막 admin boss
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    await link_user(uow_factory, boss, "deal_owner")

    # when: 다른 요청자가 boss를 삭제한다
    with pytest.raises(InvalidStateError, match="마지막 관리자"):
        await admin.delete_user.execute(user_id=boss.id, actor=OTHER_ADMIN_ACTOR)

    # then: 마지막 관리자 오류이고 boss는 재직이다
    async with uow_factory() as uow:
        assert (await uow.users.get(boss.id)).is_active


async def test_self_protection_also_applies_to_the_resign_branch(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """자기 삭제 금지는 연결이 있어도 적용된다

    테스트 코드: US-065
    """
    # given: 연결이 있는 admin root
    me = await seed_user(uow_factory, "root", Role.ADMIN)
    await seed_user(uow_factory, "boss", Role.ADMIN)
    await link_user(uow_factory, me, "deal_owner")

    # when: root가 자기 자신을 삭제한다
    with pytest.raises(InvalidStateError, match="자기 자신"):
        await admin.delete_user.execute(user_id=me.id, actor=me.to_principal())
    # then: 자기 자신 오류다


async def test_a_resigned_admin_is_not_counted_as_an_active_admin(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """퇴사한 admin은 재직 admin 수에 세지 않는다

    테스트 코드: US-066
    """
    # given: 퇴사 처리한 admin boss
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    await link_user(uow_factory, boss, "deal_owner")
    await admin.delete_user.execute(user_id=boss.id, actor=root.to_principal())

    # when: 남은 admin root를 삭제한다
    with pytest.raises(InvalidStateError, match="마지막 관리자"):
        await admin.delete_user.execute(user_id=root.id, actor=OTHER_ADMIN_ACTOR)
    # then: 마지막 관리자 오류다


async def test_physical_delete_blocked_by_a_late_reference_falls_back_to_resign(
    admin: AdminStack,
    uow: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """연결 확인 뒤 물리 삭제가 막히면 퇴사 처리로 바뀐다"""
    # given: 연결을 놓치는 has_links와 연결이 있는 kim
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, target, "deal_owner")

    # when: kim을 삭제한다
    with pytest.raises(UserInUseError):  # 전제: 이 Fake는 연결이 있으면 물리 삭제를 거부한다
        await uow.users.delete(target.id)

    # then: 결과가 resigned이고 kim은 퇴사 상태다
    async def no_links_seen(_: object) -> bool:
        return False

    monkeypatch.setattr(uow.users, "has_links", no_links_seen)
    outcome = await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    assert outcome is DeleteOutcome.RESIGNED
    async with uow_factory() as active:
        assert not (await active.users.get(target.id)).is_active


async def test_resigned_user_leaves_the_default_list_and_shows_in_the_resigned_list(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """퇴사 처리된 사용자는 기본 목록에서 빠지고 퇴사 목록에 퇴사 정보와 함께 보인다.

    테스트 코드: US-060
    """
    # given: 연결이 있는 kim
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, target, "deal_owner")

    # when: kim을 삭제해 퇴사 처리한다
    outcome = await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    # then: 기본 목록에는 없고 퇴사 목록에 퇴사 시각과 함께 있다
    assert outcome is DeleteOutcome.RESIGNED
    assert [u.login_id.value for u in await admin.list_users.execute()] == ["root"]
    resigned = await admin.list_users.execute(status=UserStatusFilter.RESIGNED)
    assert [(u.login_id.value, u.deleted_at) for u in resigned] == [("kim", NOW)]


@pytest.mark.parametrize("linked", [False, True])
async def test_deleted_or_resigned_local_user_cannot_sign_in_again(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory, linked: bool
) -> None:
    """삭제·퇴사된 local 사용자는 같은 비밀번호로 다시 로그인할 수 없다.

    테스트 코드: US-061
    """
    # given: 비밀번호 해시가 있는 local 사용자 kim(연결이 있으면 퇴사, 없으면 삭제된다)
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_local_user(uow_factory, "kim", "kim-password-1")
    if linked:
        await link_user(uow_factory, target, "deal_owner")

    # when: kim을 삭제한다
    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    # then: 같은 비밀번호로 로그인하면 인증 오류다
    with pytest.raises(AuthenticationError):
        await auth.password_login.execute(
            login_id="kim", password=Password("kim-password-1"), client_ip="10.0.0.1"
        )
