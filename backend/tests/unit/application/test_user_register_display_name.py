"""AC-25: RegisterUser의 선택 display_name (정규화·저장·거절)."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import NAME_MAX, Role
from app.domain.common.errors import InvalidValueError
from tests.fakes.admin_stack import ADMIN_ACTOR
from tests.support.admin_seed import active_logins

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack


async def test_register_user_stores_the_given_display_name(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    user = await admin.register_user.execute(
        login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR, display_name="김영업"
    )

    assert user.display_name == "김영업"
    assert user.last_login_at is None
    async with uow_factory() as uow:
        stored = await uow.users.get(user.id)
    assert stored.display_name == "김영업"


async def test_list_users_shows_the_registered_display_name_before_the_first_login(
    admin: AdminStack,
) -> None:
    await admin.register_user.execute(
        login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR, display_name="김영업"
    )

    listed = [u for u in await admin.list_users.execute() if u.login_id.value == "kim"]

    assert [(u.display_name, u.last_login_at) for u in listed] == [("김영업", None)]


@pytest.mark.parametrize("value", [None, "", "   "])
async def test_register_user_without_a_usable_display_name_stores_none(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, value: str | None
) -> None:
    user = await admin.register_user.execute(
        login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR, display_name=value
    )

    async with uow_factory() as uow:
        assert (await uow.users.get(user.id)).display_name is None


async def test_register_user_default_display_name_is_none(admin: AdminStack) -> None:
    user = await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)

    assert user.display_name is None


async def test_register_user_trims_the_display_name(admin: AdminStack) -> None:
    user = await admin.register_user.execute(
        login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR, display_name="  김영업  "
    )

    assert user.display_name == "김영업"


async def test_register_user_accepts_a_display_name_of_name_max(admin: AdminStack) -> None:
    user = await admin.register_user.execute(
        login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR, display_name="가" * NAME_MAX
    )

    assert user.display_name == "가" * NAME_MAX


@pytest.mark.parametrize("value", ["가" * (NAME_MAX + 1), "a\x00b"])
async def test_register_user_rejects_an_invalid_display_name_and_stores_nothing(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, value: str
) -> None:
    with pytest.raises(InvalidValueError):
        await admin.register_user.execute(
            login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR, display_name=value
        )

    assert await active_logins(uow_factory) == []
