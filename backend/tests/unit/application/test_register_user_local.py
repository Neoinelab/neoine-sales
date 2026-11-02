"""RegisterUser의 local 모드 (AC-6): 비밀번호·이름 필수, 해시는 같은 트랜잭션에 저장.

AD 모드(방식 미선택인 기존 시스템 포함)에서는 비밀번호를 받지 않고 이름은 선택이다(기존 동작).
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError, InvalidValueError
from tests.fakes.admin_stack import ADMIN_ACTOR
from tests.support.admin_seed import active_logins
from tests.support.auth_seed import seed_auth_mode, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.entities import User
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

PW = "Passw0rd-ok"  # 가짜 값


async def _register(admin: AdminStack, login_id: str = "kim", **kwargs: object) -> User:
    values: dict[str, object] = {
        "role": Role.SALES,
        "display_name": "김영업",
        "password": Password(PW),
        **kwargs,
    }
    return await admin.register_user.execute(login_id=login_id, actor=ADMIN_ACTOR, **values)  # type: ignore[arg-type]


@pytest.fixture
async def local_mode(uow_factory: UnitOfWorkFactory) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)


@pytest.mark.usefixtures("local_mode")
async def test_register_user_local_saves_user_profile_and_hash(
    admin: AdminStack, auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    user = await _register(admin, email=" Kim@Corp.TEST ", phone="010-1234-5678")

    stored = await uow.users.get(user.id)
    assert (stored.display_name, stored.email, stored.phone) == (
        "김영업",
        "kim@corp.test",
        "010-1234-5678",
    )
    assert stored.created_by_user_id == ADMIN_ACTOR.user_id
    saved = await uow.password_hashes.get(user.id)
    assert saved is not None
    assert await auth.hasher.verify(Password(PW), saved) is True


@pytest.mark.usefixtures("local_mode")
async def test_register_user_local_requires_password(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    with pytest.raises(InvalidValueError):
        await _register(admin, password=None)

    assert await active_logins(uow_factory) == []


@pytest.mark.usefixtures("local_mode")
@pytest.mark.parametrize("password", ["short7!", "1234567", "kim"])
async def test_register_user_local_rejects_a_weak_password_and_stores_nothing(
    admin: AdminStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, password: str
) -> None:
    with pytest.raises(InvalidValueError):
        await _register(admin, password=Password(password))

    assert await active_logins(uow_factory) == []
    assert uow.password_hashes._items == {}


@pytest.mark.usefixtures("local_mode")
@pytest.mark.parametrize("name", [None, "", "   "])
async def test_register_user_local_requires_display_name(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, name: str | None
) -> None:
    with pytest.raises(InvalidValueError):
        await _register(admin, display_name=name)

    assert await active_logins(uow_factory) == []


@pytest.mark.usefixtures("local_mode")
@pytest.mark.parametrize("profile", [{"email": "abc"}, {"phone": "12"}])
async def test_register_user_local_rejects_invalid_email_or_phone(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, profile: dict[str, str]
) -> None:
    with pytest.raises(InvalidValueError):
        await _register(admin, **profile)

    assert await active_logins(uow_factory) == []


@pytest.mark.usefixtures("local_mode")
async def test_register_user_local_rejects_a_reserved_login_id(admin: AdminStack) -> None:
    with pytest.raises(InvalidValueError):
        await _register(admin, "dev-sales")


@pytest.mark.usefixtures("local_mode")
async def test_register_user_local_rejects_a_duplicate_active_login_id(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    first = await _register(admin, "kim")
    hashes = dict(uow.password_hashes._items)

    with pytest.raises(AlreadyExistsError):
        await _register(admin, "KIM", display_name="다른 사람")

    assert await active_logins(uow_factory) == ["kim"]
    assert uow.password_hashes._items == hashes
    assert (await uow.users.get(first.id)).display_name == "김영업"


@pytest.mark.usefixtures("local_mode")
async def test_register_user_local_allows_a_resigned_login_id_to_register_again(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "kim", Role.SALES, resigned=True)

    user = await _register(admin, "kim")

    assert user.is_active


@pytest.mark.usefixtures("local_mode")
async def test_registered_local_user_can_sign_in_with_the_password(
    admin: AdminStack, auth: AuthStack
) -> None:
    await _register(admin, "kim")

    outcome = await auth.password_login.execute(
        login_id="kim", password=Password(PW), client_ip="10.0.0.1"
    )

    assert outcome.session.principal.subject == "kim"


@pytest.mark.usefixtures("local_mode")
async def test_register_user_local_hashes_outside_any_transaction(
    admin: AdminStack, auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    seen: list[int] = []
    original = auth.hasher.hash

    async def spy(password: Password):  # type: ignore[no-untyped-def]  # noqa: ANN202
        seen.append(uow.open_units)
        return await original(password)

    auth.hasher.hash = spy  # type: ignore[method-assign]

    await _register(admin)

    assert seen == [0]


# ---- AD 모드 ----


@pytest.mark.parametrize("mode", [AuthMode.AD, None])
async def test_register_user_ad_rejects_password(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, mode: AuthMode | None
) -> None:
    if mode is not None:
        await seed_auth_mode(uow_factory, mode)

    with pytest.raises(InvalidValueError):
        await _register(admin)

    assert await active_logins(uow_factory) == []


@pytest.mark.parametrize("mode", [AuthMode.AD, None])
async def test_register_user_ad_accepts_phone_and_email_and_stores_no_hash(
    admin: AdminStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, mode: AuthMode | None
) -> None:
    if mode is not None:
        await seed_auth_mode(uow_factory, mode)

    user = await _register(
        admin, password=None, display_name=None, email="kim@corp.test", phone="010-1234-5678"
    )

    stored = await uow.users.get(user.id)
    assert (stored.display_name, stored.email, stored.phone) == (
        None,
        "kim@corp.test",
        "010-1234-5678",
    )
    assert await uow.password_hashes.get(user.id) is None
    assert stored.login_id == LoginId("kim")


async def test_register_user_ad_rejects_an_invalid_phone(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.AD)

    with pytest.raises(InvalidValueError):
        await _register(admin, password=None, phone="12")

    assert await active_logins(uow_factory) == []
