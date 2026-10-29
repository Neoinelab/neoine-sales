"""ldap3 어댑터(MOCK_SYNC): 서비스 계정 search-then-bind 인증 흐름·속성·이스케이프·실패 분류 (AC7).

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
    user = await login(directory)

    assert user == DirectoryUser(login_id="kim", display_name="김영업", email="kim@corp.test")


async def test_login_id_is_passed_through_normalized(directory: MockDirectory) -> None:
    user = await login(directory, " KIM ")

    assert user.login_id == "kim"


async def test_login_binds_service_account_then_user_dn(directory: MockDirectory) -> None:
    await login(directory)

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
    hostile = cast("LoginId", SimpleNamespace(value="x,ou=admins+cn=y"))

    with pytest.raises(InvalidCredentialsError):
        await make_adapter(directory).authenticate(
            make_directory_settings(), BASE_DN, hostile, Password(PASSWORD)
        )

    assert [call[1] for call in directory.factory_calls] == [BIND_ACCOUNT]  # 사용자 바인드 없음


async def test_login_filter_escapes_login_id(directory: MockDirectory) -> None:
    directory.add_entry(
        "cn=a*b(c)\\\\d,ou=users,dc=corp,dc=test", user_attributes("a*b(c)\\d", PASSWORD)
    )
    hostile = cast("LoginId", SimpleNamespace(value="a*b(c)\\d"))

    user = await make_adapter(directory).authenticate(
        make_directory_settings(), BASE_DN, hostile, Password(PASSWORD)
    )

    assert user.display_name == "a*b(c)\\d"
    search = directory.connections[0].search_args[-1]
    assert search["search_filter"] == r"(&(objectClass=user)(sAMAccountName=a\2ab\28c\29\5cd))"


async def test_search_uses_the_given_base_dn_subtree_and_limits_results(
    directory: MockDirectory,
) -> None:
    await login(directory)

    search = directory.connections[0].search_args[-1]
    assert search["search_base"] == BASE_DN
    assert search["size_limit"] == 2
    attributes = search["attributes"]
    assert isinstance(attributes, list)
    assert set(attributes) >= {"displayName", "mail"}
    assert "SUBTREE" in str(search["search_scope"]).upper()


async def test_login_does_not_read_the_root_dse(directory: MockDirectory) -> None:
    """Base DN은 저장된 값을 쓰고 로그인마다 다시 찾지 않는다."""
    await login(directory)

    assert all(
        args.get("search_base") != "" for c in directory.connections for args in c.search_args
    )


async def test_login_reads_display_name_and_mail(directory: MockDirectory) -> None:
    directory.add_user("lee", PASSWORD, display_name="이름A", mail="a@corp.test")

    user = await login(directory, "lee")

    assert (user.display_name, user.email) == ("이름A", "a@corp.test")


async def test_missing_display_name_falls_back_to_login_id(directory: MockDirectory) -> None:
    directory.add_user("bare", PASSWORD)

    user = await login(directory, "bare")

    assert user == DirectoryUser(login_id="bare", display_name="bare", email=None)


async def test_no_entry_is_invalid_credentials_at_search(directory: MockDirectory) -> None:
    error = await failure(directory, login_id="nobody")

    assert type(error) is InvalidCredentialsError
    assert error.stage is VerificationStage.SEARCH
    assert len(directory.connections) == 1  # 사용자 바인드까지 가지 않는다


async def test_filter_without_match_is_invalid_credentials_at_search(
    directory: MockDirectory,
) -> None:
    error = await failure(
        directory, user_filter="(&(objectClass=user)(sAMAccountName=zz{login_id}))"
    )

    assert type(error) is InvalidCredentialsError
    assert error.stage is VerificationStage.SEARCH


async def test_two_entries_is_misconfigured_at_search(directory: MockDirectory) -> None:
    directory.add_user("dup", PASSWORD)
    directory.add_entry("cn=dup2,ou=staff,dc=corp,dc=test", user_attributes("dup", PASSWORD))

    error = await failure(directory, login_id="dup")

    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SEARCH
    assert len(directory.connections) == 1  # 어느 쪽 비밀번호도 시도하지 않는다


async def test_search_failure_under_base_dn_is_misconfigured_base_dn(
    directory: MockDirectory,
) -> None:
    error = await failure(directory, base_dn="dc=missing,dc=test")

    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.BASE_DN


async def test_wrong_service_password_is_misconfigured_service_bind(
    directory: MockDirectory,
) -> None:
    error = await failure(directory, bind_password="Not-the-service-pw")  # noqa: S106

    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SERVICE_BIND
    assert directory.calls.count("search") == 0


SIZE_LIMIT_EXCEEDED = 4


async def test_size_limit_exceeded_is_misconfigured_at_search_not_base_dn(
    directory: MockDirectory,
) -> None:
    """3건 이상이면 AD가 결과 코드 4를 준다. 2건 이상과 같은 SEARCH 오설정이다(BASE_DN 아님)."""
    directory.add_entry("cn=kim2,ou=staff,dc=corp,dc=test", user_attributes("kim", PASSWORD))
    directory.user_search_code = SIZE_LIMIT_EXCEEDED

    error = await failure(directory)

    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SEARCH
    assert len(directory.connections) == 1  # 사용자 비밀번호를 시도하지 않는다


@pytest.mark.parametrize("code", [49, 50, 53])
async def test_service_account_rejection_is_misconfigured_service_bind(
    directory: MockDirectory, code: int
) -> None:
    directory.bind_codes_by_user[BIND_ACCOUNT] = code

    error = await failure(directory)

    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SERVICE_BIND


@pytest.mark.parametrize("code", [51, 52])
async def test_other_service_bind_failure_is_unavailable(
    directory: MockDirectory, code: int
) -> None:
    directory.bind_codes_by_user[BIND_ACCOUNT] = code

    error = await failure(directory)

    assert type(error) is DirectoryUnavailableError
    assert error.stage is VerificationStage.SERVICE_BIND


async def test_wrong_user_password_is_invalid_credentials_at_bind(directory: MockDirectory) -> None:
    error = await failure(directory, attempt="Wrong-password-1")

    assert type(error) is InvalidCredentialsError
    assert error.stage is VerificationStage.BIND


@pytest.mark.parametrize("code", [49, 50, 53])
async def test_user_bind_rejection_codes_are_invalid_credentials(
    directory: MockDirectory, code: int
) -> None:
    directory.bind_codes_by_user[USER_DN] = code

    error = await failure(directory)

    assert type(error) is InvalidCredentialsError
    assert error.stage is VerificationStage.BIND


@pytest.mark.parametrize("code", [51, 52])
async def test_server_side_user_bind_failures_are_unavailable_not_credentials(
    directory: MockDirectory, code: int
) -> None:
    directory.bind_codes_by_user[USER_DN] = code

    error = await failure(directory)

    assert isinstance(error, DirectoryUnavailableError)
    assert not isinstance(error, InvalidCredentialsError)


async def test_empty_user_password_does_not_connect(directory: MockDirectory) -> None:
    empty = cast(
        "Password", SimpleNamespace(reveal=lambda: "")
    )  # Password는 빈 값을 만들 수 없으므로 방어 계층만 확인한다

    with pytest.raises(InvalidCredentialsError):
        await make_adapter(directory).authenticate(
            make_directory_settings(), BASE_DN, LoginId("kim"), empty
        )

    assert directory.factory_calls == []
    assert directory.log == []
