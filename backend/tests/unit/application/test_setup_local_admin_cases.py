"""최초 설정 3단계 첫 admin 등록, 앱에서 직접 관리(local) 흐름(SetupFirstLocalAdmin).

SU-029~SU-038 중 local 부분.

password 칸 위치(`errors[].location`)와 빈 비밀번호의 422는 web 규칙이라
`tests/unit/web/test_setup_routes.py`에서 확인한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import STORAGE_FIRST
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import WeakPasswordError
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError, InvalidStateError, InvalidValueError
from tests.support.auth_seed import active_admin_logins, seed_auth_mode, seed_storage, seed_user

if TYPE_CHECKING:
    from app.application.auth.issue_session import IssuedSession
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

STRONG = "Passw0rd-ok"  # 가짜 값
IP = "10.0.0.1"
ID_RULE = "로그인 아이디는 영문 소문자·숫자·점·밑줄·하이픈으로 64자 이하여야 합니다"


@pytest.fixture
async def local_ready(uow_factory: UnitOfWorkFactory) -> None:
    """방식 local, 저장 위치가 등록된 상태(AD 설정 없음)."""
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    await seed_storage(uow_factory)


async def _register(
    auth: AuthStack,
    login_id: str = "boss",
    password: str = STRONG,
    profile: dict[str, str | None] | None = None,
) -> IssuedSession:
    values: dict[str, str | None] = {"display_name": "보스", **(profile or {})}
    return await auth.setup.execute(
        login_id=login_id, password=Password(password), client_ip=IP, **values
    )


@pytest.mark.usefixtures("local_ready")
async def test_local_input_creates_the_first_admin_and_signs_in(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """local 방식에서 입력한 아이디·비밀번호·이름으로 첫 admin이 만들어지고 로그인된다.

    테스트 코드: SU-032
    """
    # when: 아이디·비밀번호·이름·이메일·전화로 첫 admin을 등록한다
    #   (전제: 방식 local, 저장 위치가 등록되었다)
    issued = await _register(auth, profile={"email": "boss@corp.test", "phone": "02-123-4567"})

    # then: 입력값으로 admin 주체가 만들어지고 세션으로 인증된다
    principal = issued.principal
    assert (principal.subject, principal.name, principal.email, principal.role) == (
        "boss",
        "보스",
        "boss@corp.test",
        Role.ADMIN,
    )
    assert (await auth.authenticate.execute(issued.token)).subject == "boss"
    # then: 사용자 전화, 해시가 저장되었고 AD 호출·시도 제한 기록은 없다
    user = await uow.users.get_active_by_login_id(LoginId("boss"))
    assert user is not None
    assert (user.role, user.phone) == (Role.ADMIN, "02-123-4567")
    saved_hash = await uow.password_hashes.get(user.id)
    assert saved_hash is not None
    assert await auth.hasher.verify(Password(STRONG), saved_hash)
    assert auth.directory.authenticate_calls == []
    assert uow.login_failures._items == {}
    # then: 진행 상태는 셋 다 끝났다
    status = await auth.status.execute()
    assert (status.needs_directory_setup, status.needs_storage_setup, status.needs_admin_setup) == (
        False,
        False,
        False,
    )


@pytest.mark.usefixtures("local_ready")
async def test_omitted_email_and_phone_are_stored_as_none(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """이메일·전화를 생략하면 null로 저장된다.

    테스트 코드: SU-032
    """
    # when: 이메일·전화 없이 등록한다 (전제: 방식 local, 저장 위치가 등록되었다)
    await _register(auth)

    # then: 사용자의 이메일·전화는 None이다
    user = await uow.users.get_active_by_login_id(LoginId("boss"))
    assert user is not None
    assert (user.email, user.phone) == (None, None)


@pytest.mark.usefixtures("local_ready")
@pytest.mark.parametrize("password", ["short7!", "  BOSS  "], ids=["7-chars", "equals-id"])
async def test_a_weak_password_is_rejected_and_the_setup_stays_open(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, password: str
) -> None:
    """local 비밀번호가 8자 미만이거나 아이디와 같으면 거절되고 설정은 열린 채다.

    테스트 코드: SU-033
    """
    # when: 아이디 boss에 7자 비밀번호, 앞뒤 공백이 붙은 8자 "  BOSS  "로 등록한다
    #   (전제: 방식 local, 저장 위치가 등록되었다)
    with pytest.raises(WeakPasswordError) as caught:
        await _register(auth, password=password)

    # then: 각각 8자 이상 안내와 아이디 동일 안내이고 설정은 열린 채다
    expected = (
        "비밀번호는 8자 이상이어야 합니다"
        if len(password) < 8
        else "비밀번호는 아이디와 같을 수 없습니다"
    )
    assert str(caught.value) == expected
    assert await active_admin_logins(uow_factory) == []
    assert (await auth.status.execute()).needs_admin_setup is True


@pytest.mark.usefixtures("local_ready")
async def test_an_eight_character_password_is_allowed(auth: AuthStack) -> None:
    """8자 비밀번호는 허용한다(조합 규칙 없음).

    테스트 코드: SU-033
    """
    # when: 8자 비밀번호 "Passw0rd"로 등록한다 (전제: 방식 local, 저장 위치가 등록되었다)
    issued = await _register(auth, password="Passw0rd")  # noqa: S106 - 가짜 값

    # then: 등록된다
    assert issued.principal.role is Role.ADMIN


@pytest.mark.usefixtures("local_ready")
@pytest.mark.parametrize(
    ("profile", "message"),
    [
        ({"display_name": None}, "이름은(는) 비어 있을 수 없습니다"),
        ({"display_name": "   "}, "이름은(는) 비어 있을 수 없습니다"),
        ({"display_name": "가" * 201}, "이름은(는) 200자를 넘을 수 없습니다"),
        ({"email": "not-mail"}, "이메일 형식이 올바르지 않습니다."),
        ({"phone": "abc"}, "전화번호 형식이 올바르지 않습니다."),
    ],
    ids=["no-name", "blank-name", "201-chars", "bad-email", "bad-phone"],
)
async def test_an_invalid_profile_is_rejected_and_the_setup_stays_open(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, profile: dict[str, str | None], message: str
) -> None:
    """local 이름이 없거나 길거나 이메일·전화 형식이 틀리면 거절되고 설정은 열린 채다.

    테스트 코드: SU-035
    """
    # when: 이름 없음·공백·201자, 이메일 "not-mail", 전화 "abc"로 각각 등록한다
    #   (전제: 방식 local, 저장 위치가 등록되었다)
    with pytest.raises(InvalidValueError) as caught:
        await _register(auth, profile=profile)

    # then: 해당 문구이고 사용자가 생기지 않으며 admin 단계는 그대로다
    assert str(caught.value) == message
    assert await active_admin_logins(uow_factory) == []
    assert (await auth.status.execute()).needs_admin_setup is True


@pytest.mark.usefixtures("local_ready")
async def test_the_login_id_is_trimmed_and_lowercased(auth: AuthStack, uow: FakeUnitOfWork) -> None:
    """local 아이디는 앞뒤 공백을 지우고 소문자로 맞춘다.

    테스트 코드: SU-036
    """
    # when: 아이디 " Boss "로 등록한다 (전제: 방식 local, 저장 위치가 등록되었다)
    issued = await _register(auth, " Boss ")

    # then: 사용자의 아이디는 boss다
    assert issued.principal.subject == "boss"
    assert await uow.users.get_active_by_login_id(LoginId("boss")) is not None


@pytest.mark.usefixtures("local_ready")
@pytest.mark.parametrize("login_id", ["bad id!", "-boss", "a" * 65], ids=["space", "hyphen", "65"])
async def test_a_malformed_login_id_is_rejected(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, login_id: str
) -> None:
    """local 아이디 형식이 틀리면 거절된다.

    테스트 코드: SU-036
    """
    # when: "bad id!"·"-boss"·65자 아이디로 등록한다 (전제: 방식 local, 저장 위치가 등록되었다)
    with pytest.raises(InvalidValueError) as caught:
        await _register(auth, login_id)

    # then: 아이디 형식 안내이고 아무도 등록되지 않는다
    assert str(caught.value) == ID_RULE
    assert await active_admin_logins(uow_factory) == []


async def test_without_a_storage_path_the_registration_is_storage_first_and_uses_no_counter(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """local 방식에서 저장 위치가 없으면 첫 admin 등록은 409이고 시도 제한을 쓰지 않는다.

    테스트 코드: SU-037
    """
    # given: 방식 local이고 저장 위치가 없다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)

    # when: 올바른 입력으로 첫 admin을 등록한다
    with pytest.raises(InvalidStateError) as caught:
        await _register(auth)

    # then: "파일 저장 위치를 먼저 설정하세요."이고 사용자가 없으며 시도 제한 기록이 없다
    assert str(caught.value) == STORAGE_FIRST
    assert await active_admin_logins(uow_factory) == []
    assert uow.login_failures._items == {}


@pytest.mark.usefixtures("local_ready")
async def test_an_existing_active_login_id_is_already_exists_in_local_mode(
    auth: AuthStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """같은 아이디의 재직 사용자가 있으면 local 첫 admin 등록은 already-exists이고 승격하지 않는다.

    테스트 코드: SU-029
    """
    # given: local 방식에 저장 위치가 있고 재직 사용자 kim이 있다
    await seed_user(uow_factory, "kim", Role.SALES)

    # when: kim으로 첫 admin을 등록한다
    with pytest.raises(AlreadyExistsError) as caught:
        await _register(auth, "kim")

    # then: "이미 존재하는 사용자입니다: kim"이고 kim은 sales 그대로, 설정은 열린 채
    assert str(caught.value) == "이미 존재하는 사용자입니다: kim"
    existing = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert existing is not None
    assert existing.role is Role.SALES
    assert (await auth.status.execute()).needs_admin_setup is True


@pytest.mark.usefixtures("local_ready")
async def test_a_mode_switched_to_ad_during_hashing_is_a_409(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """해시 계산 뒤 방식이 ad로 바뀌었으면 local 첫 admin 등록은 409이고 아무도 등록되지 않는다.

    테스트 코드: SU-031
    """
    # given: local 방식 등록에서 해시 계산 뒤 방식이 ad로 바뀌어 있다
    original = auth.hasher.hash

    async def switch_to_ad(password: Password):  # type: ignore[no-untyped-def]  # noqa: ANN202
        await seed_auth_mode(uow_factory, AuthMode.AD)
        return await original(password)

    auth.hasher.hash = switch_to_ad  # type: ignore[method-assign]

    # when: 등록이 저장 단계에 이른다
    with pytest.raises(InvalidStateError) as caught:
        await auth.setup_local_admin.execute(
            login_id="boss", password=Password(STRONG), display_name="보스"
        )

    # then: "앱에서 계정을 직접 관리할 때만 쓸 수 있습니다."이고 사용자·해시가 생기지 않는다
    assert str(caught.value) == "앱에서 계정을 직접 관리할 때만 쓸 수 있습니다."
    assert await uow.users.get_active_by_login_id(LoginId("boss")) is None
    assert uow.password_hashes._items == {}


@pytest.mark.usefixtures("local_ready")
@pytest.mark.parametrize(
    ("raw", "normalized"),
    [("dev-admin", "dev-admin"), ("DEV-SALES", "dev-sales"), ("dev-user", "dev-user")],
)
async def test_reserved_ids_are_rejected_in_local_mode_and_a_normal_account_still_works(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, raw: str, normalized: str
) -> None:
    """local 방식에서 예약 아이디로는 첫 admin을 만들 수 없고 이후 일반 계정으로는 된다.

    테스트 코드: SU-038
    """
    # given: local 방식(저장 위치 등록)이다
    with pytest.raises(InvalidValueError) as caught:
        await _register(auth, raw)
    # when: 예약 아이디로 등록하고, 이어서 일반 계정 kim으로 등록한다
    issued = await _register(auth, "kim")

    # then: 예약 아이디는 정규화한 아이디가 담긴 문구의 422이고 kim 등록은 성공한다
    assert str(caught.value) == f"개발 로그인 전용 아이디는 등록할 수 없습니다: {normalized}"
    assert issued.principal.subject == "kim"
    assert await active_admin_logins(uow_factory) == ["kim"]
