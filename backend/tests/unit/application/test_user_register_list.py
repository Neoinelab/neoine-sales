"""사용자 목록·등록 유스케이스 (USER-1·2·3, T-U27~U28)."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError, InvalidValueError
from tests.factories import NOW, later
from tests.fakes.admin_stack import ADMIN_ACTOR, OTHER_ADMIN_ACTOR
from tests.support.admin_seed import active_logins
from tests.support.auth_seed import seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.directory import FakeDirectoryAuthenticator
    from tests.fakes.unit_of_work import FakeUnitOfWork


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_register_user_stores_the_chosen_role(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, role: Role
) -> None:
    """AD 모드에서 아이디·역할로 등록하면 그 역할의 재직 사용자가 저장되고 등록자는 기록되지 않는다

    테스트 코드: US-001
    """
    # when: admin이 역할을 정해 사용자를 등록한다
    user = await admin.register_user.execute(login_id="new.hire", role=role, actor=ADMIN_ACTOR)

    # then: 재직 사용자가 그 역할로 저장되고 등록 시각이 채워지며 로그인 기록·등록자 필드는 없다
    assert (user.login_id.value, user.role) == ("new.hire", role)
    assert user.created_at == NOW
    assert not hasattr(user, "created_by_user_id")
    assert user.is_active
    assert (user.display_name, user.email, user.last_login_at) == (
        None,
        None,
        None,
    )
    async with uow_factory() as uow:
        stored = await uow.users.get(user.id)
    assert (stored.login_id.value, stored.role) == ("new.hire", role)


async def test_register_user_by_another_admin_stores_no_creator_and_leaves_no_link(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """다른 admin이 등록해도 등록자는 어디에도 기록되지 않아 그 admin에게 연결이 생기지 않는다

    테스트 코드: US-001
    """
    # when: 다른 admin이 kim을 등록한다
    user = await admin.register_user.execute(
        login_id="kim", role=Role.SALES, actor=OTHER_ADMIN_ACTOR
    )

    # then: 사용자에 등록자 필드가 없고, 등록한 admin은 연결(has_links)이 없다
    assert not hasattr(user, "created_by_user_id")
    async with uow_factory() as uow:
        assert not await uow.users.has_links(OTHER_ADMIN_ACTOR.user_id)


@pytest.mark.parametrize(
    "reserved", ["dev-admin", "dev-sales", "dev-user", "DEV-ADMIN", "DEV-Sales", " dev-user "]
)
async def test_register_user_rejects_the_reserved_dev_login_ids(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, reserved: str
) -> None:
    """예약된 개발 로그인 아이디는 대소문자·공백과 무관하게 등록할 수 없다

    테스트 코드: US-005
    """
    # when: 예약 아이디로 등록한다
    with pytest.raises(InvalidValueError):
        await admin.register_user.execute(login_id=reserved, role=Role.SALES, actor=ADMIN_ACTOR)

    # then: 입력 오류이고 사용자가 저장되지 않는다
    assert await active_logins(uow_factory) == []


async def test_register_user_accepts_a_dev_prefixed_login_id_that_is_not_reserved(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """예약 아이디가 아닌 dev- 아이디는 일반 아이디로 등록된다.

    테스트 코드: US-006
    """
    # when: 예약 목록에 없는 dev-qa를 등록한다
    user = await admin.register_user.execute(login_id="dev-qa", role=Role.SALES, actor=ADMIN_ACTOR)

    # then: 등록되어 재직자 목록에 있다
    assert user.login_id.value == "dev-qa"
    assert await active_logins(uow_factory) == ["dev-qa"]


async def test_register_user_normalizes_the_login_id(admin: AdminStack) -> None:
    """아이디의 앞뒤 공백과 대문자는 정규화되어 저장된다

    테스트 코드: US-002
    """
    # when: 공백과 대문자가 섞인 아이디로 등록한다
    user = await admin.register_user.execute(
        login_id="  Kim.Lee ", role=Role.USER, actor=ADMIN_ACTOR
    )

    # then: 소문자·공백 없는 아이디로 저장된다
    assert user.login_id.value == "kim.lee"


async def test_register_user_does_not_ask_the_directory(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    """등록은 AD에 계정이 있는지 묻지 않는다

    테스트 코드: US-010
    """
    # when: AD에 없는 아이디를 등록한다 (전제: Fake 디렉터리에 없는 계정)
    await admin.register_user.execute(login_id="not-in-ad", role=Role.SALES, actor=ADMIN_ACTOR)

    # then: 디렉터리 인증·탐색 호출이 하나도 없다
    assert directory.authenticate_calls == []
    assert directory.discover_calls == []


async def test_register_user_accepts_a_64_character_login_id(admin: AdminStack) -> None:
    """64자 아이디는 등록된다

    테스트 코드: US-003
    """
    # when: 64자 아이디로 등록한다
    user = await admin.register_user.execute(login_id="a" * 64, role=Role.SALES, actor=ADMIN_ACTOR)

    # then: 그 아이디로 저장된다
    assert user.login_id.value == "a" * 64


@pytest.mark.parametrize(
    "login_id", ["", "   ", "-lead", ".lead", "a b", "한글", "a,b", "a=b", "a" * 65, "a\x00b"]
)
async def test_register_user_rejects_a_malformed_login_id(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, login_id: str
) -> None:
    """형식에 맞지 않거나 65자인 아이디는 거절되고 저장되지 않는다

    테스트 코드: US-004
    """
    # when: 형식이 틀린 아이디로 등록한다
    with pytest.raises(InvalidValueError):
        await admin.register_user.execute(login_id=login_id, role=Role.SALES, actor=ADMIN_ACTOR)

    # then: 입력 오류이고 사용자가 저장되지 않는다
    assert await active_logins(uow_factory) == []


@pytest.mark.parametrize("duplicate", ["kim", "KIM", " Kim "])
async def test_register_user_rejects_an_active_duplicate(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, duplicate: str
) -> None:
    """재직 중인 아이디는 대소문자·공백이 달라도 중복 오류다

    테스트 코드: US-007
    """
    # given: 재직 kim
    await seed_user(uow_factory, "kim", Role.SALES)

    # when: 표기가 다른 같은 아이디로 등록한다
    with pytest.raises(AlreadyExistsError):
        await admin.register_user.execute(login_id=duplicate, role=Role.ADMIN, actor=ADMIN_ACTOR)

    # then: 이미 존재 오류이고 재직자는 kim 하나뿐이다
    assert await active_logins(uow_factory) == ["kim"]


async def test_duplicate_active_login_id_is_rejected_without_adding_a_user(
    admin: AdminStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """중복 등록이 거절되면 사용자 수는 그대로다

    테스트 코드: US-007
    """
    # given: 재직 kim
    await seed_user(uow_factory, "kim", Role.SALES)
    before = len(uow.users._items)

    # when: 같은 아이디로 등록한다
    with pytest.raises(AlreadyExistsError):
        await admin.register_user.execute(login_id="kim", role=Role.ADMIN, actor=ADMIN_ACTOR)

    # then: 이미 존재 오류이고 저장된 사용자 수가 늘지 않는다
    assert len(uow.users._items) == before


async def test_register_user_allows_a_login_id_whose_user_was_physically_deleted(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """물리 삭제된 아이디는 다시 등록되고 새 id를 받는다

    테스트 코드: US-009
    """
    # given: 물리 삭제된 kim
    old = await seed_user(uow_factory, "kim", Role.SALES, deleted=True)

    # when: 같은 아이디로 다시 등록한다
    user = await admin.register_user.execute(login_id="kim", role=Role.USER, actor=ADMIN_ACTOR)

    # then: 예전과 다른 id의 재직 사용자가 생긴다
    assert user.id != old.id
    assert user.role is Role.USER
    assert await active_logins(uow_factory) == ["kim"]


async def test_list_users_returns_only_active_users_in_creation_order(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """기본 목록은 재직자만 등록 순서로 보인다

    테스트 코드: US-023
    """
    # given: 재직 2명과 물리 삭제된 1명
    await seed_user(uow_factory, "amy", Role.ADMIN, now=later(1))
    await seed_user(uow_factory, "gone", Role.SALES, deleted=True, now=later(2))
    await seed_user(uow_factory, "bob", Role.USER, now=later(3))

    # when: 기본 조건으로 목록을 읽는다
    users = await admin.list_users.execute()

    # then: 재직자만 등록 순서대로 나온다
    assert [(u.login_id.value, u.role) for u in users] == [
        ("amy", Role.ADMIN),
        ("bob", Role.USER),
    ]


async def test_list_users_exposes_the_last_login_time(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """로그인한 사용자는 마지막 로그인 시각이 목록에 있다

    테스트 코드: US-029
    """
    # given: 로그인 기록이 있는 kim
    user = await seed_user(uow_factory, "kim", Role.SALES)
    user.record_login(NOW, display_name="김영업", email="kim@corp.test")
    async with uow_factory() as active:
        await active.users.update(user)
        await active.commit()

    # when: 목록을 읽는다
    (listed,) = await admin.list_users.execute()

    # then: 마지막 로그인 시각과 AD 프로필이 보인다
    assert listed.last_login_at == NOW
    assert (listed.display_name, listed.email) == ("김영업", "kim@corp.test")


async def test_list_users_pages_with_offset_and_limit(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """offset·limit으로 한 페이지를 받는다

    테스트 코드: US-026
    """
    # given: 사용자 3명
    for n, name in enumerate(("u1", "u2", "u3"), start=1):
        await seed_user(uow_factory, name, Role.USER, now=later(n))

    # when: offset 1, limit 1로 읽는다
    page = await admin.list_users.execute(offset=1, limit=1)

    # then: 둘째 사용자만 나온다
    assert [u.login_id.value for u in page] == ["u2"]


@pytest.mark.parametrize(("offset", "limit"), [(-1, 10), (0, 0), (0, 201)])
async def test_list_users_rejects_out_of_range_paging(
    admin: AdminStack, offset: int, limit: int
) -> None:
    """범위 밖 페이지 값은 입력 오류다

    테스트 코드: US-027
    """
    # when: 범위 밖 offset·limit으로 읽는다
    with pytest.raises(InvalidValueError):
        await admin.list_users.execute(offset=offset, limit=limit)
    # then: 입력 오류다
