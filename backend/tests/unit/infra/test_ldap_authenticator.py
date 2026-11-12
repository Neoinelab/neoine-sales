"""ldap3 어댑터(MOCK_SYNC): 서비스 계정 search-then-bind 인증 흐름·속성·이스케이프·실패 분류.

흐름: 서비스 계정 바인드 -> 저장된 Base DN 아래 사용자 필터로 최대 2건 검색 -> 1건이면 그 항목 DN과
사용자 비밀번호로 새 연결 바인드. 로그인 아이디는 DN에 넣지 않고 LDAP 필터 값으로만 쓴다.

미검증(모의 서버 한계): 실제 LDAPS/StartTLS 협상, UPN·DOMAIN\\id 서비스 계정 바인드,
AD 하위 오류 코드, 한글 속성, 실제 타임아웃, RootDSE 실제 응답(테스트가 모의 응답으로 대신한다).
문서의 '미검증 영역' 참고.
"""

from types import SimpleNamespace
from typing import cast

import pytest

from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    DirectoryUser,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.auth.credentials import LoginId, Password
from tests.factories_auth import BASE_DN, BIND_ACCOUNT, BIND_PASSWORD
from tests.factories_directory import make_directory_settings
from tests.support.ldap_adapter import PASSWORD, failure, login, make_adapter
from tests.support.ldap_mock import MockDirectory, user_attributes

USER_DN = "cn=kim,ou=users,dc=corp,dc=test"


async def test_valid_credentials_return_directory_user_with_attributes(
    directory: MockDirectory,
) -> None:
    """올바른 자격 증명이면 디렉터리 속성을 담은 DirectoryUser를 돌려준다."""
    # when: 올바른 자격 증명으로 로그인한다 (전제: 모의 디렉터리에 kim이 있다)
    user = await login(directory)

    # then: 아이디·표시 이름·이메일이 담긴다
    assert user == DirectoryUser(login_id="kim", display_name="김영업", email="kim@corp.test")


async def test_login_id_is_passed_through_normalized(directory: MockDirectory) -> None:
    """로그인 아이디는 정규화되어 전달된다."""
    # when: 대문자와 공백이 든 아이디로 로그인한다
    user = await login(directory, " KIM ")

    # then: 소문자 아이디로 돌아온다
    assert user.login_id == "kim"


async def test_login_binds_service_account_then_user_dn(directory: MockDirectory) -> None:
    """로그인은 서비스 계정으로 먼저 바인드하고, 찾은 항목의 DN으로 새 연결에서 다시 바인드한다."""
    # when: 로그인한다
    await login(directory)

    # then: 서비스 계정 바인드 뒤 검색, 그다음 사용자 DN 바인드이고 연결은 모두 닫힌다
    first, second = directory.factory_calls
    assert (first[1], first[2]) == (BIND_ACCOUNT, BIND_PASSWORD)  # 1) 서비스 계정
    assert (second[1], second[2]) == (USER_DN, PASSWORD)  # 2) 찾은 항목의 DN + 사용자 비밀번호
    assert len(directory.connections) == 2  # 사용자 바인드는 새 연결로 한다
    assert directory.calls.count("bind") == 2
    assert directory.calls.count("search") == 1
    assert directory.calls.index("search") < len(directory.calls) - 1 - directory.calls[::-1].index(
        "bind"
    )
    assert directory.calls[-1] == "unbind"
    assert directory.calls.count("unbind") >= 2  # 두 연결 모두 닫는다


async def test_login_never_builds_a_bind_name_from_the_login_id(directory: MockDirectory) -> None:
    """로그인 아이디로 바인드 이름을 만들지 않는다."""
    # given: DN 주입을 노린 아이디
    hostile = cast("LoginId", SimpleNamespace(value="x,ou=admins+cn=y"))

    # when·then: 로그인하면 자격 증명 오류가 난다
    with pytest.raises(InvalidCredentialsError):
        await make_adapter(directory).authenticate(
            make_directory_settings(), BASE_DN, hostile, Password(PASSWORD)
        )

    # then: 서비스 계정 바인드만 있었고 사용자 바인드는 없다
    assert [call[1] for call in directory.factory_calls] == [BIND_ACCOUNT]  # 사용자 바인드 없음


async def test_login_filter_escapes_login_id(directory: MockDirectory) -> None:
    """로그인 아이디의 특수문자는 LDAP 필터에서 이스케이프된다."""
    # given: 특수문자가 든 아이디의 항목과 그 아이디
    directory.add_entry(
        "cn=a*b(c)\\\\d,ou=users,dc=corp,dc=test", user_attributes("a*b(c)\\d", PASSWORD)
    )
    hostile = cast("LoginId", SimpleNamespace(value="a*b(c)\\d"))

    # when: 그 아이디로 로그인한다
    user = await make_adapter(directory).authenticate(
        make_directory_settings(), BASE_DN, hostile, Password(PASSWORD)
    )

    # then: 그 항목으로 로그인되고 검색 필터는 이스케이프되어 있다
    assert user.display_name == "a*b(c)\\d"
    search = directory.connections[0].search_args[-1]
    assert search["search_filter"] == r"(&(objectClass=user)(sAMAccountName=a\2ab\28c\29\5cd))"


async def test_search_uses_the_given_base_dn_subtree_and_limits_results(
    directory: MockDirectory,
) -> None:
    """검색은 주어진 Base DN 아래 하위 트리에서 최대 2건으로 제한해 한다."""
    # when: 로그인한다
    await login(directory)

    # then: 검색 기준·크기 제한·요청 속성·범위가 기대와 같다
    search = directory.connections[0].search_args[-1]
    assert search["search_base"] == BASE_DN
    assert search["size_limit"] == 2
    attributes = search["attributes"]
    assert isinstance(attributes, list)
    assert set(attributes) >= {"displayName", "mail"}
    assert "SUBTREE" in str(search["search_scope"]).upper()


async def test_login_does_not_read_the_root_dse(directory: MockDirectory) -> None:
    """Base DN은 저장된 값을 쓰고 로그인마다 다시 찾지 않는다."""
    # when: 로그인한다
    await login(directory)

    # then: RootDSE(빈 검색 기준)를 읽지 않았다
    assert all(
        args.get("search_base") != "" for c in directory.connections for args in c.search_args
    )


async def test_login_reads_display_name_and_mail(directory: MockDirectory) -> None:
    """로그인은 displayName과 mail 속성을 읽는다."""
    # given: 표시 이름과 메일이 있는 사용자
    directory.add_user("lee", PASSWORD, display_name="이름A", mail="a@corp.test")

    # when: 그 사용자로 로그인한다
    user = await login(directory, "lee")

    # then: 표시 이름과 이메일이 속성 값이다
    assert (user.display_name, user.email) == ("이름A", "a@corp.test")


async def test_missing_display_name_falls_back_to_login_id(directory: MockDirectory) -> None:
    """표시 이름 속성이 없으면 로그인 아이디를 이름으로 쓴다."""
    # given: 속성이 없는 사용자
    directory.add_user("bare", PASSWORD)

    # when: 그 사용자로 로그인한다
    user = await login(directory, "bare")

    # then: 이름은 아이디이고 이메일은 없다
    assert user == DirectoryUser(login_id="bare", display_name="bare", email=None)


async def test_no_entry_is_invalid_credentials_at_search(directory: MockDirectory) -> None:
    """검색 결과가 없으면 검색 단계의 자격 증명 오류다."""
    # when: 없는 아이디로 로그인해 실패를 받는다
    error = await failure(directory, login_id="nobody")

    # then: 검색 단계의 InvalidCredentialsError이고 사용자 바인드까지 가지 않는다
    assert type(error) is InvalidCredentialsError
    assert error.stage is VerificationStage.SEARCH
    assert len(directory.connections) == 1  # 사용자 바인드까지 가지 않는다


async def test_filter_without_match_is_invalid_credentials_at_search(
    directory: MockDirectory,
) -> None:
    """필터에 맞는 항목이 없으면 검색 단계의 자격 증명 오류다."""
    # when: 아무것도 찾지 못하는 필터로 로그인해 실패를 받는다
    error = await failure(
        directory, user_filter="(&(objectClass=user)(sAMAccountName=zz{login_id}))"
    )

    # then: 검색 단계의 InvalidCredentialsError다
    assert type(error) is InvalidCredentialsError
    assert error.stage is VerificationStage.SEARCH


async def test_two_entries_is_misconfigured_at_search(directory: MockDirectory) -> None:
    """항목이 둘 이상이면 검색 단계의 설정 오류다."""
    # given: 같은 아이디의 항목 두 개
    directory.add_user("dup", PASSWORD)
    directory.add_entry("cn=dup2,ou=staff,dc=corp,dc=test", user_attributes("dup", PASSWORD))

    # when: 그 아이디로 로그인해 실패를 받는다
    error = await failure(directory, login_id="dup")

    # then: 검색 단계의 설정 오류이고 사용자 비밀번호는 시도하지 않는다
    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SEARCH
    assert len(directory.connections) == 1  # 어느 쪽 비밀번호도 시도하지 않는다


async def test_search_failure_under_base_dn_is_misconfigured_base_dn(
    directory: MockDirectory,
) -> None:
    """Base DN 아래 검색이 실패하면 Base DN 단계의 설정 오류다."""
    # when: 없는 Base DN으로 로그인해 실패를 받는다
    error = await failure(directory, base_dn="dc=missing,dc=test")

    # then: BASE_DN 단계의 설정 오류다
    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.BASE_DN


async def test_wrong_service_password_is_misconfigured_service_bind(
    directory: MockDirectory,
) -> None:
    """서비스 계정 비밀번호가 틀리면 서비스 바인드 단계의 설정 오류다."""
    # when: 틀린 서비스 비밀번호로 로그인해 실패를 받는다
    error = await failure(directory, bind_password="Not-the-service-pw")  # noqa: S106

    # then: SERVICE_BIND 단계의 설정 오류이고 검색은 하지 않았다
    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SERVICE_BIND
    assert directory.calls.count("search") == 0


SIZE_LIMIT_EXCEEDED = 4


async def test_size_limit_exceeded_is_misconfigured_at_search_not_base_dn(
    directory: MockDirectory,
) -> None:
    """3건 이상이면 AD가 결과 코드 4를 준다. 2건 이상과 같은 SEARCH 오설정이다(BASE_DN 아님)."""
    # given: 같은 아이디의 항목이 더 있고 AD가 크기 초과 코드를 돌려준다
    directory.add_entry("cn=kim2,ou=staff,dc=corp,dc=test", user_attributes("kim", PASSWORD))
    directory.user_search_code = SIZE_LIMIT_EXCEEDED

    # when: 결과 건수 초과(코드 4) 상황에서 로그인한다
    error = await failure(directory)

    # then: 검색 단계의 설정 오류이고 사용자 비밀번호는 시도하지 않는다
    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SEARCH
    assert len(directory.connections) == 1  # 사용자 비밀번호를 시도하지 않는다


@pytest.mark.parametrize("code", [49, 50, 53])
async def test_service_account_rejection_is_misconfigured_service_bind(
    directory: MockDirectory, code: int
) -> None:
    """서비스 계정 바인드가 거절 코드(49·50·53)면 서비스 바인드 단계의 설정 오류다."""
    # given: 서비스 계정 바인드가 해당 코드로 거절된다
    directory.bind_codes_by_user[BIND_ACCOUNT] = code

    # when: 서비스 바인드가 거절 코드로 실패하는 상황에서 로그인한다
    error = await failure(directory)

    # then: SERVICE_BIND 단계의 설정 오류다
    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SERVICE_BIND


@pytest.mark.parametrize("code", [51, 52])
async def test_other_service_bind_failure_is_unavailable(
    directory: MockDirectory, code: int
) -> None:
    """서비스 계정 바인드의 그 밖 실패 코드(51·52)는 서비스 바인드 단계의 사용 불가다."""
    # given: 서비스 계정 바인드가 해당 코드로 실패한다
    directory.bind_codes_by_user[BIND_ACCOUNT] = code

    # when: 서비스 바인드가 51·52로 실패하는 상황에서 로그인한다
    error = await failure(directory)

    # then: SERVICE_BIND 단계의 DirectoryUnavailableError다
    assert type(error) is DirectoryUnavailableError
    assert error.stage is VerificationStage.SERVICE_BIND


async def test_wrong_user_password_is_invalid_credentials_at_bind(directory: MockDirectory) -> None:
    """사용자 비밀번호가 틀리면 바인드 단계의 자격 증명 오류다."""
    # when: 틀린 비밀번호로 로그인해 실패를 받는다
    error = await failure(directory, attempt="Wrong-password-1")

    # then: BIND 단계의 InvalidCredentialsError다
    assert type(error) is InvalidCredentialsError
    assert error.stage is VerificationStage.BIND


@pytest.mark.parametrize("code", [49, 50, 53])
async def test_user_bind_rejection_codes_are_invalid_credentials(
    directory: MockDirectory, code: int
) -> None:
    """사용자 바인드가 거절 코드(49·50·53)면 바인드 단계의 자격 증명 오류다."""
    # given: 사용자 바인드가 해당 코드로 거절된다
    directory.bind_codes_by_user[USER_DN] = code

    # when: 사용자 바인드가 거절 코드로 실패하는 상황에서 로그인한다
    error = await failure(directory)

    # then: BIND 단계의 InvalidCredentialsError다
    assert type(error) is InvalidCredentialsError
    assert error.stage is VerificationStage.BIND


@pytest.mark.parametrize("code", [51, 52])
async def test_server_side_user_bind_failures_are_unavailable_not_credentials(
    directory: MockDirectory, code: int
) -> None:
    """사용자 바인드의 서버 쪽 실패(51·52)는 자격 증명 오류가 아니라 사용 불가다."""
    # given: 사용자 바인드가 해당 코드로 실패한다
    directory.bind_codes_by_user[USER_DN] = code

    # when: 사용자 바인드가 51·52로 실패하는 상황에서 로그인한다
    error = await failure(directory)

    # then: DirectoryUnavailableError이고 자격 증명 오류는 아니다
    assert isinstance(error, DirectoryUnavailableError)
    assert not isinstance(error, InvalidCredentialsError)


async def test_empty_user_password_does_not_connect(directory: MockDirectory) -> None:
    """빈 사용자 비밀번호는 연결하지 않고 거부한다."""
    # given: 빈 값을 돌려주는 비밀번호
    empty = cast(
        "Password", SimpleNamespace(reveal=lambda: "")
    )  # Password는 빈 값을 만들 수 없으므로 방어 계층만 확인한다

    # when·then: 로그인하면 자격 증명 오류가 난다
    with pytest.raises(InvalidCredentialsError):
        await make_adapter(directory).authenticate(
            make_directory_settings(), BASE_DN, LoginId("kim"), empty
        )

    # then: 디렉터리에 연결하지 않았다
    assert directory.factory_calls == []
    assert directory.log == []
