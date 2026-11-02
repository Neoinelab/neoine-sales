"""local 모드 최초 설정 3단계 SetupFirstLocalAdmin과 디스패처 SetupAdmin (AC-4).

AD를 부르지 않고 아이디·비밀번호·이름(필수)·이메일·전화로 첫 admin을 만들고 세션을 발급한다.
검증할 기존 자격증명이 없으므로 로그인 시도 제한은 쓰지 않는다. 실패하면 설정은 열린 채 남는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_FIRST, SETUP_CLOSED, STORAGE_FIRST
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError, InvalidStateError, InvalidValueError
from tests.factories import NOW
from tests.support.auth_seed import (
    active_admin_logins,
    seed_auth_mode,
    seed_directory,
    seed_storage,
    seed_user,
)

if TYPE_CHECKING:
    from app.application.auth.issue_session import IssuedSession
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

STRONG = "Passw0rd-ok"  # 가짜 값
IP = "10.0.0.1"


@pytest.fixture
async def local_ready(uow_factory: UnitOfWorkFactory) -> None:
    """local 모드로 1·2단계를 마친 상태(AD 설정 없음)."""
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    await seed_storage(uow_factory)


async def _setup(
    auth: AuthStack,
    login_id: str = "kim",
    password: str = STRONG,
    **profile: str | None,
) -> IssuedSession:
    values: dict[str, str | None] = {"display_name": "김관리", **profile}
    return await auth.setup_local_admin.execute(
        login_id=login_id, password=Password(password), **values
    )


@pytest.mark.usefixtures("local_ready")
async def test_local_setup_registers_admin_with_hash_and_profile_without_directory(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    issued = await _setup(auth, " Kim ", email=" Kim@Corp.TEST ", phone="010-1234-5678")

    admin = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert admin is not None
    assert (admin.role, admin.created_by_user_id) == (Role.ADMIN, admin.id)
    assert (admin.display_name, admin.email, admin.phone) == (
        "김관리",
        "kim@corp.test",
        "010-1234-5678",
    )
    assert admin.last_login_at == NOW
    assert issued.principal.user_id == admin.id
    stored = await uow.password_hashes.get(admin.id)
    assert stored is not None
    assert await auth.hasher.verify(Password(STRONG), stored) is True
    assert auth.directory.authenticate_calls == []
    assert auth.directory.discover_calls == []


@pytest.mark.usefixtures("local_ready")
async def test_local_setup_signs_the_admin_in(auth: AuthStack) -> None:
    issued = await _setup(auth)

    principal = await auth.authenticate.execute(issued.token)

    assert (principal.subject, principal.role, principal.name) == ("kim", Role.ADMIN, "김관리")


@pytest.mark.usefixtures("local_ready")
async def test_local_setup_profile_email_and_phone_are_optional(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    await _setup(auth)

    admin = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert admin is not None
    assert (admin.email, admin.phone) == (None, None)


@pytest.mark.usefixtures("local_ready")
@pytest.mark.parametrize("password", ["short7!", "1234567", "kim", "KIM"])
async def test_local_setup_rejects_weak_password_and_stays_open(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, password: str
) -> None:
    with pytest.raises(InvalidValueError):
        await _setup(auth, "kim", password)

    assert await active_admin_logins(uow_factory) == []
    assert uow.sessions._items == {}
    assert uow.password_hashes._items == {}
    status = await auth.status.execute()
    assert status.needs_admin_setup is True


@pytest.mark.usefixtures("local_ready")
async def test_local_setup_rejects_a_password_equal_to_the_login_id(auth: AuthStack) -> None:
    with pytest.raises(InvalidValueError):
        await _setup(auth, "kim.lee1", "Kim.Lee1")


@pytest.mark.usefixtures("local_ready")
@pytest.mark.parametrize("name", [None, "", "   "])
async def test_local_setup_requires_display_name(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, name: str | None
) -> None:
    with pytest.raises(InvalidValueError):
        await _setup(auth, display_name=name)

    assert await active_admin_logins(uow_factory) == []


@pytest.mark.usefixtures("local_ready")
@pytest.mark.parametrize("profile", [{"email": "abc"}, {"phone": "12"}])
async def test_local_setup_rejects_invalid_email_or_phone_and_stays_open(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, profile: dict[str, str]
) -> None:
    with pytest.raises(InvalidValueError):
        await _setup(auth, **profile)

    assert await active_admin_logins(uow_factory) == []


@pytest.mark.usefixtures("local_ready")
@pytest.mark.parametrize("login_id", ["dev-admin", "dev-sales", "dev-user"])
async def test_local_setup_rejects_reserved_login_id(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, login_id: str
) -> None:
    with pytest.raises(InvalidValueError):
        await _setup(auth, login_id)

    assert await active_admin_logins(uow_factory) == []


@pytest.mark.usefixtures("local_ready")
@pytest.mark.parametrize("login_id", ["", "한글", "kim)(uid=*", "a b"])
async def test_local_setup_rejects_a_malformed_login_id(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, login_id: str
) -> None:
    with pytest.raises(InvalidValueError):
        await _setup(auth, login_id)

    assert await active_admin_logins(uow_factory) == []


@pytest.mark.usefixtures("local_ready")
async def test_local_setup_after_admin_is_setup_closed(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "boss", Role.ADMIN)

    with pytest.raises(InvalidStateError) as caught:
        await _setup(auth)

    assert str(caught.value) == SETUP_CLOSED
    assert await active_admin_logins(uow_factory) == ["boss"]


async def test_local_setup_before_storage_is_storage_first(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)

    with pytest.raises(InvalidStateError) as caught:
        await _setup(auth)

    assert str(caught.value) == STORAGE_FIRST
    assert await active_admin_logins(uow_factory) == []


@pytest.mark.usefixtures("local_ready")
async def test_local_setup_with_an_existing_active_login_id_is_already_exists(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "kim", Role.SALES)

    with pytest.raises(AlreadyExistsError):
        await _setup(auth, "kim")

    assert await active_admin_logins(uow_factory) == []


@pytest.mark.usefixtures("local_ready")
async def test_local_setup_does_not_touch_the_login_attempt_counters(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    with pytest.raises(InvalidValueError):
        await _setup(auth, "kim", "short")
    await _setup(auth)

    assert uow.login_failures._items == {}


@pytest.mark.usefixtures("local_ready")
async def test_local_setup_hashes_outside_any_transaction(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """scrypt 계산 동안 DB 트랜잭션을 잡지 않는다(해시는 열린 UoW 밖에서 계산)."""
    seen: list[int] = []
    original = auth.hasher.hash

    async def spy(password: Password):  # type: ignore[no-untyped-def]  # noqa: ANN202
        seen.append(uow.open_units)
        return await original(password)

    auth.hasher.hash = spy  # type: ignore[method-assign]

    await _setup(auth)

    assert seen == [0]


# ---- 디스패처 SetupAdmin ----


@pytest.mark.usefixtures("local_ready")
async def test_dispatcher_in_local_mode_registers_locally_and_never_calls_the_directory(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    issued = await auth.setup.execute(
        login_id="kim",
        password=Password(STRONG),
        client_ip=IP,
        display_name="김관리",
        phone="010-1234-5678",
    )

    admin = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert admin is not None
    assert (admin.phone, issued.principal.role) == ("010-1234-5678", Role.ADMIN)
    assert auth.directory.authenticate_calls == []


async def test_dispatcher_in_ad_mode_authenticates_against_the_directory(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)
    await seed_storage(uow_factory)

    await auth.setup.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    admin = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert admin is not None
    assert (admin.display_name, admin.email) == ("김영업", "kim@corp.test")  # AD 프로필
    assert len(auth.directory.authenticate_calls) == 1


async def test_dispatcher_without_mode_and_directory_is_directory_first(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_storage(uow_factory)

    with pytest.raises(InvalidStateError) as caught:
        await auth.setup.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    assert str(caught.value) == DIRECTORY_FIRST


async def test_dispatcher_without_a_mode_row_but_with_a_directory_uses_the_ad_flow(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    await seed_storage(uow_factory)

    issued = await auth.setup.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    assert issued.principal.subject == "kim"
    assert len(auth.directory.authenticate_calls) == 1


@pytest.mark.parametrize(
    "profile", [{"display_name": "x"}, {"email": "a@b.co"}, {"phone": "010-1234-5678"}]
)
async def test_ad_setup_with_profile_fields_is_invalid_value(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    profile: dict[str, str],
) -> None:
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)
    await seed_storage(uow_factory)

    with pytest.raises(InvalidValueError):
        await auth.setup.execute(
            login_id="kim", password=Password("pw-kim"), client_ip=IP, **profile
        )

    assert await active_admin_logins(uow_factory) == []
    assert auth.directory.authenticate_calls == []
    assert uow.sessions._items == {}


@pytest.mark.usefixtures("local_ready")
async def test_local_setup_rechecks_the_mode_just_before_registering(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """해시 계산 뒤 잠금 안에서 방식이 여전히 local인지 다시 본다(순차: 그 사이 AD로 바뀜)."""
    original = auth.hasher.hash

    async def switch_to_ad(password: Password):  # type: ignore[no-untyped-def]  # noqa: ANN202
        await seed_auth_mode(uow_factory, AuthMode.AD)
        return await original(password)

    auth.hasher.hash = switch_to_ad  # type: ignore[method-assign]

    with pytest.raises(InvalidStateError):
        await _setup(auth)

    assert await active_admin_logins(uow_factory) == []
    assert await uow.users.get_active_by_login_id(LoginId("kim")) is None
    assert uow.sessions._items == {}
    assert uow.password_hashes._items == {}


async def test_ad_setup_rechecks_the_mode_just_before_registering(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """AD 인증 도중 방식이 local로 바뀌면 등록 직전 재확인으로 거절된다(순차 시나리오)."""
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)
    await seed_storage(uow_factory)
    original = auth.directory.authenticate

    async def switch_to_local(*args, **kwargs):  # type: ignore[no-untyped-def]  # noqa: ANN002, ANN003, ANN202
        found = await original(*args, **kwargs)
        await seed_auth_mode(uow_factory, AuthMode.LOCAL)
        return found

    auth.directory.authenticate = switch_to_local  # type: ignore[method-assign]

    with pytest.raises(InvalidStateError):
        await auth.setup_admin.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    assert await active_admin_logins(uow_factory) == []
    assert await uow.users.get_active_by_login_id(LoginId("kim")) is None
    assert uow.sessions._items == {}
    assert uow.password_hashes._items == {}
