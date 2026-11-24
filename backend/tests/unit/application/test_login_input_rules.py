"""AD 로그인 입력 규칙(AU): 형식이 틀린 아이디, 이름·이메일 정리.

DirectoryLogin 유스케이스를 Fake UoW·Fake AD 위에서 호출한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import LOGIN_FAILED
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from tests.support.auth_seed import seed_directory, seed_user, set_user_phone

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.directory import FakeDirectoryAuthenticator
    from tests.fakes.unit_of_work import FakeUnitOfWork

IP = "10.0.0.1"
NAME_MAX = 200


@pytest.fixture(autouse=True)
async def _ready(uow_factory: UnitOfWorkFactory) -> None:
    """AD 설정이 있고 kim(sales)이 등록되어 있다. AD에도 kim 계정이 있다."""
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)


@pytest.mark.parametrize(
    "login_id",
    [
        "",
        "   ",
        "a" * 65,
        "a" * 128,
        "김영업",
        "k*m",
        "k m",
        "k(m",
        "k)m",
        "k\\m",
        "k,m",
        "k=m",
        ".kim",
        "-kim",
    ],
)
async def test_malformed_login_id_is_the_common_failure_and_is_not_counted(
    auth: AuthStack, directory: FakeDirectoryAuthenticator, uow: FakeUnitOfWork, login_id: str
) -> None:
    """형식이 틀린 아이디는 401이고 AD를 부르지 않으며 시도에 세지 않는다.

    테스트 코드: AU-016
    """
    # when: 정규화한 값이 아이디 형식에 맞지 않는 아이디로 로그인한다
    #   (전제: AD 설정과 등록된 kim이 있다 (fixture))
    with pytest.raises(AuthenticationError) as caught:
        await auth.login.execute(login_id=login_id, password=Password("pw-kim"), client_ip=IP)

    # then: 공통 실패 문구이고 AD 호출·세션·실패 횟수 기록이 없다
    assert type(caught.value) is AuthenticationError
    assert str(caught.value) == LOGIN_FAILED
    assert directory.authenticate_calls == []
    assert uow.sessions._items == {}
    assert uow.login_failures._items == {}


async def test_login_truncates_a_long_directory_name_to_200_chars(
    auth: AuthStack, directory: FakeDirectoryAuthenticator, uow: FakeUnitOfWork
) -> None:
    """AD의 긴 이름은 200자로 자른다.

    테스트 코드: AU-006
    """
    # given: AD 표시 이름이 250자인 kim
    directory.add_account("kim", "pw-kim", display_name="가" * 250, email="kim@corp.test")
    # when: kim이 로그인한다
    outcome = await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    # then: users 행의 이름이 200자이고 응답의 이름도 같다
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.display_name == "가" * NAME_MAX
    assert outcome.session.principal.name == "가" * NAME_MAX


@pytest.mark.parametrize("email", ["no-at-sign", "a" * 250 + "@corp.test", "   "])
async def test_login_clears_a_malformed_directory_email(
    auth: AuthStack, directory: FakeDirectoryAuthenticator, uow: FakeUnitOfWork, email: str
) -> None:
    """AD의 이메일이 비었거나 254자를 넘거나 @가 없으면 비운다.

    테스트 코드: AU-006
    """
    # given: 이메일 형식이 틀린 AD 계정 kim
    directory.add_account("kim", "pw-kim", display_name="김영업", email=email)
    # when: kim이 로그인한다
    await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    # then: users 행의 이메일이 비어 있다
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.email is None


@pytest.mark.parametrize("telephone", ["02-123-4567", "+82 2-123-4567"])
async def test_login_uses_the_telephone_number_when_the_mobile_is_blank(
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
    uow: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    telephone: str,
) -> None:
    """AD의 mobile이 없거나 비었으면 어댑터가 고른 telephoneNumber 값으로 덮어쓴다.

    테스트 코드: AU-090
    """
    # given: 앱에서 입력한 전화가 있는 kim, AD 어댑터가 mobile 대신 telephoneNumber를 고른 계정
    #   (mobile 없음·공백 판정은 ldap 어댑터 단위 테스트가 검증한다)
    await set_user_phone(uow_factory, "kim", "02-111-2222")
    directory.add_account(
        "kim", "pw-kim", display_name="김영업", email="kim@corp.test", phone=telephone
    )

    # when: kim이 로그인한다
    await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    # then: 저장된 전화는 telephoneNumber 값이다
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.phone == telephone


@pytest.mark.parametrize(
    ("directory_phone", "stored"),
    [
        ("010-1234\u0000-5678", "010-1234-5678"),
        ("0" * 40, "0" * 40),
        ("1" * 39 + "  " + "2" * 4, "1" * 39),
        ("가" * 41, "가" * 40),
    ],
    ids=["nul-removed", "exactly-40", "trailing-space-after-cut", "41-chars-cut"],
)
async def test_login_cleans_and_truncates_the_directory_phone(
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
    uow: FakeUnitOfWork,
    directory_phone: str,
    stored: str,
) -> None:
    """AD 전화번호는 NUL·앞뒤 공백을 지우고 40자를 넘으면 앞 40자로 자르고 끝 공백을 지운다.

    테스트 코드: AU-092
    """
    # given: 정리가 필요한 전화번호를 주는 AD 계정
    directory.add_account(
        "kim", "pw-kim", display_name="김영업", email="kim@corp.test", phone=directory_phone
    )

    # when: kim이 로그인한다
    outcome = await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    # then: 로그인은 성공하고 저장된 전화는 정리·자른 값이다
    assert outcome.session.principal.subject == "kim"
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.phone == stored
    assert len(stored) <= 40


async def test_login_keeps_the_stored_phone_when_the_directory_phone_is_only_nul(
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
    uow: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
) -> None:
    """NUL을 지운 뒤 비는 AD 전화번호는 값이 없는 것으로 보고 기존 전화번호를 유지한다.

    테스트 코드: AU-092
    """
    # given: 앱에서 입력한 전화가 있는 kim과 NUL만 있는 AD 전화
    await set_user_phone(uow_factory, "kim", "02-111-2222")
    directory.add_account("kim", "pw-kim", display_name="김영업", phone="\u0000\u0000")

    # when: kim이 로그인한다
    await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    # then: 전화는 그대로다
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.phone == "02-111-2222"
