"""RegisterUser의 선택 display_name (정규화·저장·거절)."""

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
    """AD 모드 등록의 이름은 주면 그대로 저장된다

    테스트 코드: US-012
    """
    # when: 이름을 주고 등록한다
    user = await admin.register_user.execute(
        login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR, display_name="김영업"
    )

    # then: 이름이 저장되고 마지막 로그인은 없다
    assert user.display_name == "김영업"
    assert user.last_login_at is None
    async with uow_factory() as uow:
        stored = await uow.users.get(user.id)
    assert stored.display_name == "김영업"


async def test_list_users_shows_the_registered_display_name_before_the_first_login(
    admin: AdminStack,
) -> None:
    """등록한 이름은 첫 로그인 전에도 목록에 보인다

    테스트 코드: US-012
    """
    # given: 이름을 주고 등록한 kim
    await admin.register_user.execute(
        login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR, display_name="김영업"
    )

    # when: 목록을 읽는다
    listed = [u for u in await admin.list_users.execute() if u.login_id.value == "kim"]

    # then: 이름이 보이고 마지막 로그인은 null이다
    assert [(u.display_name, u.last_login_at) for u in listed] == [("김영업", None)]


@pytest.mark.parametrize("value", [None, "", "   "])
async def test_register_user_without_a_usable_display_name_stores_none(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, value: str | None
) -> None:
    """이름을 생략하거나 비우면 이름 없음으로 저장된다

    테스트 코드: US-012
    """
    # when: 이름 없이(null·빈 값·공백) 등록한다
    user = await admin.register_user.execute(
        login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR, display_name=value
    )

    # then: 저장된 이름은 None이다
    async with uow_factory() as uow:
        assert (await uow.users.get(user.id)).display_name is None


async def test_register_user_default_display_name_is_none(admin: AdminStack) -> None:
    """이름 인자를 생략하면 이름 없음이다

    테스트 코드: US-012
    """
    # when: 이름 인자 없이 등록한다
    user = await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)

    # then: 이름은 None이다
    assert user.display_name is None


async def test_register_user_trims_the_display_name(admin: AdminStack) -> None:
    """이름의 앞뒤 공백은 지워진다

    테스트 코드: US-013
    """
    # when: 앞뒤 공백이 있는 이름으로 등록한다
    user = await admin.register_user.execute(
        login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR, display_name="  김영업  "
    )

    # then: 공백 없는 이름으로 저장된다
    assert user.display_name == "김영업"


async def test_register_user_accepts_a_display_name_of_name_max(admin: AdminStack) -> None:
    """최대 길이(200자) 이름은 저장된다

    테스트 코드: US-013
    """
    # when: 200자 이름으로 등록한다
    user = await admin.register_user.execute(
        login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR, display_name="가" * NAME_MAX
    )

    # then: 200자 그대로 저장된다
    assert user.display_name == "가" * NAME_MAX


@pytest.mark.parametrize("value", ["가" * (NAME_MAX + 1), "a\x00b"])
async def test_register_user_rejects_an_invalid_display_name_and_stores_nothing(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, value: str
) -> None:
    """200자를 넘거나 NUL이 든 이름은 거절되고 저장되지 않는다

    테스트 코드: US-014
    """
    # when: 201자 또는 NUL이 든 이름으로 등록한다
    with pytest.raises(InvalidValueError):
        await admin.register_user.execute(
            login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR, display_name=value
        )

    # then: 입력 오류이고 사용자가 저장되지 않는다
    assert await active_logins(uow_factory) == []
