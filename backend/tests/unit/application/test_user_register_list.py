"""사용자 목록·등록 유스케이스 (USER-1·2·3, T-U27~U28)."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError, InvalidValueError
from tests.factories import NOW, later
from tests.fakes.admin_stack import ADMIN_ACTOR, DEV_ACTOR
from tests.support.admin_seed import active_logins
from tests.support.auth_seed import seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.directory import FakeDirectoryAuthenticator


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_register_user_stores_the_chosen_role(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, role: Role
) -> None:
    user = await admin.register_user.execute(login_id="new.hire", role=role, actor=ADMIN_ACTOR)

    assert (user.login_id.value, user.role) == ("new.hire", role)
    assert (user.created_by, user.created_at) == ("root", NOW)
    assert (user.display_name, user.email, user.last_login_at) == (
        None,
        None,
        None,
    )
    async with uow_factory() as uow:
        stored = await uow.users.get(user.id)
    assert (stored.login_id.value, stored.role) == ("new.hire", role)


async def test_register_user_records_a_dev_admin_as_creator(admin: AdminStack) -> None:
    user = await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=DEV_ACTOR)

    assert user.created_by == "dev:admin"


async def test_register_user_normalizes_the_login_id(admin: AdminStack) -> None:
    user = await admin.register_user.execute(
        login_id="  Kim.Lee ", role=Role.USER, actor=ADMIN_ACTOR
    )

    assert user.login_id.value == "kim.lee"


async def test_register_user_does_not_ask_the_directory(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    await admin.register_user.execute(login_id="not-in-ad", role=Role.SALES, actor=ADMIN_ACTOR)

    assert directory.authenticate_calls == []
    assert directory.probe_calls == []


async def test_register_user_accepts_a_64_character_login_id(admin: AdminStack) -> None:
    user = await admin.register_user.execute(login_id="a" * 64, role=Role.SALES, actor=ADMIN_ACTOR)

    assert user.login_id.value == "a" * 64


@pytest.mark.parametrize(
    "login_id", ["", "   ", "-lead", ".lead", "a b", "한글", "a,b", "a=b", "a" * 65, "a\x00b"]
)
async def test_register_user_rejects_a_malformed_login_id(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, login_id: str
) -> None:
    with pytest.raises(InvalidValueError):
        await admin.register_user.execute(login_id=login_id, role=Role.SALES, actor=ADMIN_ACTOR)

    assert await active_logins(uow_factory) == []


@pytest.mark.parametrize("duplicate", ["kim", "KIM", " Kim "])
async def test_register_user_rejects_an_active_duplicate(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, duplicate: str
) -> None:
    await seed_user(uow_factory, "kim", Role.SALES)

    with pytest.raises(AlreadyExistsError):
        await admin.register_user.execute(login_id=duplicate, role=Role.ADMIN, actor=ADMIN_ACTOR)

    assert await active_logins(uow_factory) == ["kim"]


async def test_register_user_allows_a_login_id_whose_user_was_deleted(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    old = await seed_user(uow_factory, "kim", Role.SALES, deleted=True)

    user = await admin.register_user.execute(login_id="kim", role=Role.USER, actor=ADMIN_ACTOR)

    assert user.id != old.id
    assert user.role is Role.USER
    assert await active_logins(uow_factory) == ["kim"]


async def test_list_users_returns_only_active_users_in_creation_order(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "amy", Role.ADMIN, now=later(1))
    await seed_user(uow_factory, "gone", Role.SALES, deleted=True, now=later(2))
    await seed_user(uow_factory, "bob", Role.USER, now=later(3))

    users = await admin.list_users.execute()

    assert [(u.login_id.value, u.role) for u in users] == [
        ("amy", Role.ADMIN),
        ("bob", Role.USER),
    ]


async def test_list_users_exposes_the_last_login_time(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    user = await seed_user(uow_factory, "kim", Role.SALES)
    user.record_login(NOW, display_name="김영업", email="kim@corp.test")
    async with uow_factory() as active:
        await active.users.update(user)
        await active.commit()

    (listed,) = await admin.list_users.execute()

    assert listed.last_login_at == NOW
    assert (listed.display_name, listed.email) == ("김영업", "kim@corp.test")


async def test_list_users_pages_with_offset_and_limit(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    for n, name in enumerate(("u1", "u2", "u3"), start=1):
        await seed_user(uow_factory, name, Role.USER, now=later(n))

    page = await admin.list_users.execute(offset=1, limit=1)

    assert [u.login_id.value for u in page] == ["u2"]


@pytest.mark.parametrize(("offset", "limit"), [(-1, 10), (0, 0), (0, 201)])
async def test_list_users_rejects_out_of_range_paging(
    admin: AdminStack, offset: int, limit: int
) -> None:
    with pytest.raises(InvalidValueError):
        await admin.list_users.execute(offset=offset, limit=limit)
