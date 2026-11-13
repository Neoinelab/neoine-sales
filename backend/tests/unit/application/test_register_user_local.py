"""RegisterUser의 local 모드: 비밀번호·이름 필수, 해시는 같은 트랜잭션에 저장.

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
    """local 모드 등록은 프로필과 비밀번호 해시를 함께 저장한다

    테스트 코드: US-017
    """
    # when: 비밀번호·이름·이메일·전화로 등록한다 (전제: local 모드)
    user = await _register(admin, email=" Kim@Corp.TEST ", phone="010-1234-5678")

    # then: 정규화된 프로필이 저장되고 등록자 필드는 없으며 비밀번호 해시가 검증된다
    stored = await uow.users.get(user.id)
    assert (stored.display_name, stored.email, stored.phone) == (
        "김영업",
        "kim@corp.test",
        "010-1234-5678",
    )
    assert not hasattr(stored, "created_by_user_id")
    saved = await uow.password_hashes.get(user.id)
    assert saved is not None
    assert await auth.hasher.verify(Password(PW), saved) is True


@pytest.mark.usefixtures("local_mode")
async def test_register_user_local_requires_password(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """local 모드에서 비밀번호 없이 등록하면 입력 오류다

    테스트 코드: US-018
    """
    # when: 비밀번호 없이 등록한다 (전제: local 모드)
    with pytest.raises(InvalidValueError):
        await _register(admin, password=None)

    # then: 입력 오류이고 사용자가 저장되지 않는다
    assert await active_logins(uow_factory) == []


@pytest.mark.usefixtures("local_mode")
@pytest.mark.parametrize("password", ["short7!", "1234567", "kim"])
async def test_register_user_local_rejects_a_weak_password_and_stores_nothing(
    admin: AdminStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, password: str
) -> None:
    """8자 미만이거나 아이디와 같은 비밀번호는 거절되고 아무것도 저장되지 않는다

    테스트 코드: US-020
    """
    # when: 약한 비밀번호로 등록한다 (전제: local 모드)
    with pytest.raises(InvalidValueError):
        await _register(admin, password=Password(password))

    # then: 입력 오류이고 사용자·해시가 저장되지 않는다
    assert await active_logins(uow_factory) == []
    assert uow.password_hashes._items == {}


@pytest.mark.usefixtures("local_mode")
async def test_register_user_local_accepts_an_eight_character_password(
    admin: AdminStack, auth: AuthStack
) -> None:
    """비밀번호는 정확히 8자여도 등록되고 그 비밀번호로 로그인된다.

    테스트 코드: US-020
    """
    # when: 8자 비밀번호로 등록한다 (전제: local 모드)
    await _register(admin, "kim", password=Password("abcd1234"))

    # then: 그 비밀번호로 로그인된다
    outcome = await auth.password_login.execute(
        login_id="kim", password=Password("abcd1234"), client_ip="10.0.0.1"
    )
    assert outcome.session.principal.subject == "kim"


@pytest.mark.usefixtures("local_mode")
@pytest.mark.parametrize("name", [None, "", "   "])
async def test_register_user_local_requires_display_name(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, name: str | None
) -> None:
    """local 모드에서 이름이 없거나 공백뿐이면 입력 오류다

    테스트 코드: US-019
    """
    # when: 이름 없이 등록한다 (전제: local 모드)
    with pytest.raises(InvalidValueError):
        await _register(admin, display_name=name)

    # then: 입력 오류이고 사용자가 저장되지 않는다
    assert await active_logins(uow_factory) == []


@pytest.mark.usefixtures("local_mode")
@pytest.mark.parametrize("profile", [{"email": "abc"}, {"phone": "12"}])
async def test_register_user_local_rejects_invalid_email_or_phone(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, profile: dict[str, str]
) -> None:
    """형식이 틀린 이메일·전화는 거절되고 저장되지 않는다

    테스트 코드: US-015
    """
    # when: 잘못된 이메일 또는 전화로 등록한다 (전제: local 모드)
    with pytest.raises(InvalidValueError):
        await _register(admin, **profile)

    # then: 입력 오류이고 사용자가 저장되지 않는다
    assert await active_logins(uow_factory) == []


@pytest.mark.usefixtures("local_mode")
async def test_register_user_local_rejects_a_reserved_login_id(admin: AdminStack) -> None:
    """local 모드에서도 예약 아이디는 등록할 수 없다

    테스트 코드: US-005
    """
    # when: 예약 아이디로 등록한다 (전제: local 모드)
    with pytest.raises(InvalidValueError):
        await _register(admin, "dev-sales")
    # then: 입력 오류다


@pytest.mark.usefixtures("local_mode")
async def test_register_user_local_rejects_a_duplicate_active_login_id(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """local 모드에서도 재직 중인 아이디는 중복 오류이고 기존 해시·이름은 그대로다

    테스트 코드: US-007
    """
    # given: 재직 local 사용자 kim
    first = await _register(admin, "kim")
    hashes = dict(uow.password_hashes._items)

    # when: 표기가 다른 같은 아이디로 등록한다
    with pytest.raises(AlreadyExistsError):
        await _register(admin, "KIM", display_name="다른 사람")

    # then: 이미 존재 오류이고 기존 사용자·해시가 그대로다
    assert await active_logins(uow_factory) == ["kim"]
    assert uow.password_hashes._items == hashes
    assert (await uow.users.get(first.id)).display_name == "김영업"


@pytest.mark.usefixtures("local_mode")
async def test_register_user_local_allows_a_resigned_login_id_to_register_again(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """local 모드에서 퇴사한 아이디는 다시 등록된다

    테스트 코드: US-008
    """
    # given: 퇴사한 kim
    await seed_user(uow_factory, "kim", Role.SALES, resigned=True)

    # when: 같은 아이디로 등록한다
    user = await _register(admin, "kim")

    # then: 재직 사용자가 생긴다
    assert user.is_active


@pytest.mark.usefixtures("local_mode")
async def test_registered_local_user_can_sign_in_with_the_password(
    admin: AdminStack, auth: AuthStack
) -> None:
    """local 모드로 등록한 사용자는 그 비밀번호로 로그인된다

    테스트 코드: US-017
    """
    # given: 등록한 local 사용자 kim
    await _register(admin, "kim")

    # when: 그 비밀번호로 로그인한다
    outcome = await auth.password_login.execute(
        login_id="kim", password=Password(PW), client_ip="10.0.0.1"
    )

    # then: kim으로 로그인된다
    assert outcome.session.principal.subject == "kim"


@pytest.mark.usefixtures("local_mode")
async def test_register_user_local_hashes_outside_any_transaction(
    admin: AdminStack, auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """해시 계산은 열린 트랜잭션 밖에서 한다"""
    # given: 해시 호출 시점의 열린 UoW 수를 기록하는 해시기
    seen: list[int] = []
    original = auth.hasher.hash

    async def spy(password: Password):  # type: ignore[no-untyped-def]  # noqa: ANN202
        seen.append(uow.open_units)
        return await original(password)

    auth.hasher.hash = spy  # type: ignore[method-assign]

    # when: local 사용자를 등록한다
    await _register(admin)

    # then: 해시 계산 중 열린 트랜잭션이 없었다
    assert seen == [0]


# ---- AD 모드 ----


@pytest.mark.parametrize("mode", [AuthMode.AD, None])
async def test_register_user_ad_rejects_password(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, mode: AuthMode | None
) -> None:
    """AD 모드에서 비밀번호를 보내면 입력 오류이고 저장되지 않는다

    테스트 코드: US-011
    """
    # given: AD 모드(방식 행이 없는 기존 시스템 포함)
    if mode is not None:
        await seed_auth_mode(uow_factory, mode)

    # when: 비밀번호와 함께 등록한다
    with pytest.raises(InvalidValueError):
        await _register(admin)

    # then: 입력 오류이고 사용자가 저장되지 않는다
    assert await active_logins(uow_factory) == []


@pytest.mark.parametrize("mode", [AuthMode.AD, None])
async def test_register_user_ad_accepts_phone_and_email_and_stores_no_hash(
    admin: AdminStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, mode: AuthMode | None
) -> None:
    """AD 모드는 이름 없이도 등록되고 비밀번호 해시를 저장하지 않는다

    테스트 코드: US-012
    """
    # given: AD 모드
    if mode is not None:
        await seed_auth_mode(uow_factory, mode)

    # when: 이름 없이 이메일·전화만 주고 등록한다
    user = await _register(
        admin, password=None, display_name=None, email="kim@corp.test", phone="010-1234-5678"
    )

    # then: 이름은 None이고 이메일·전화가 저장되며 해시는 없다
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
    """AD 모드에서도 형식이 틀린 전화는 거절된다

    테스트 코드: US-015
    """
    # given: AD 모드
    await seed_auth_mode(uow_factory, AuthMode.AD)

    # when: 잘못된 전화로 등록한다
    with pytest.raises(InvalidValueError):
        await _register(admin, password=None, phone="12")

    # then: 입력 오류이고 사용자가 저장되지 않는다
    assert await active_logins(uow_factory) == []
