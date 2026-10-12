"""ldap3 어댑터(MOCK_SYNC): 인증 흐름·속성·이스케이프·실패 분류·probe (T-A1~A10, A13~A15).

미검증(모의 서버 한계): 실제 LDAPS 인증서 검증, StartTLS 협상 성공, 여러 DC 장애 조치,
UPN·DOMAIN\\id 바인드, AD 하위 오류 코드, 한글 속성, 실제 타임아웃. 문서의 '미검증 영역' 참고.
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
from tests.factories_auth import make_directory_settings
from tests.support.ldap_adapter import PASSWORD, failure, login, make_adapter
from tests.support.ldap_mock import MockDirectory, user_attributes


async def test_valid_credentials_return_directory_user_with_attributes(
    directory: MockDirectory,
) -> None:
    user = await login(directory)

    assert user == DirectoryUser(login_id="kim", display_name="김영업", email="kim@corp.test")


async def test_login_id_is_passed_through_normalized(directory: MockDirectory) -> None:
    user = await login(directory, " KIM ")

    assert user.login_id == "kim"


async def test_attribute_names_come_from_the_settings(directory: MockDirectory) -> None:
    directory.add_user("lee", PASSWORD, display_name="이름A", mail="a@corp.test")
    directory.add_entry(
        "cn=park,ou=users,dc=corp,dc=test",
        user_attributes("park", PASSWORD, description="박 과장", otherMailbox="park@corp.test"),
    )

    user = await login(
        directory,
        "park",
        display_name_attribute="description",
        email_attribute="otherMailbox",
    )

    assert (user.display_name, user.email) == ("박 과장", "park@corp.test")


async def test_missing_attributes_fall_back_to_login_id_and_no_email(
    directory: MockDirectory,
) -> None:
    directory.add_user("bare", PASSWORD)

    user = await login(directory, "bare")

    assert user == DirectoryUser(login_id="bare", display_name="bare", email=None)


async def test_wrong_password_is_invalid_credentials_at_bind(directory: MockDirectory) -> None:
    error = await failure(directory, attempt="Wrong-password-1")

    assert type(error) is InvalidCredentialsError
    assert error.stage is VerificationStage.BIND


async def test_unknown_account_is_invalid_credentials_at_bind(directory: MockDirectory) -> None:
    error = await failure(directory, login_id="nobody")

    assert type(error) is InvalidCredentialsError
    assert error.stage is VerificationStage.BIND


@pytest.mark.parametrize("code", [49, 50, 53])
async def test_bind_rejection_codes_are_invalid_credentials(
    directory: MockDirectory, code: int
) -> None:
    directory.bind_code = code

    error = await failure(directory)

    assert type(error) is InvalidCredentialsError
    assert error.stage is VerificationStage.BIND


@pytest.mark.parametrize("code", [51, 52])
async def test_server_side_bind_failures_are_unavailable_not_credentials(
    directory: MockDirectory, code: int
) -> None:
    directory.bind_code = code

    error = await failure(directory)

    assert isinstance(error, DirectoryUnavailableError)
    assert not isinstance(error, InvalidCredentialsError)


async def test_empty_password_never_opens_a_connection(directory: MockDirectory) -> None:
    empty = cast(
        "Password", SimpleNamespace(reveal=lambda: "")
    )  # Password는 빈 값을 만들 수 없으므로 방어 계층만 확인한다

    with pytest.raises(InvalidCredentialsError):
        await make_adapter(directory).authenticate(
            make_directory_settings(),
            LoginId("kim"),
            empty,
        )

    assert directory.factory_calls == []
    assert directory.log == []


async def test_filter_value_is_escaped_with_ldap_filter_rules(directory: MockDirectory) -> None:
    directory.add_entry(
        "cn=a*b(c)\\\\d,ou=users,dc=corp,dc=test", user_attributes("a*b(c)\\d", PASSWORD)
    )
    hostile = cast("LoginId", SimpleNamespace(value="a*b(c)\\d"))

    user = await make_adapter(directory).authenticate(
        make_directory_settings(),
        hostile,
        Password(PASSWORD),
    )

    assert user.display_name == "a*b(c)\\d"
    search = directory.connections[-1].search_args[-1]
    assert search["search_filter"] == r"(&(objectClass=user)(sAMAccountName=a\2ab\28c\29\5cd))"


async def test_dn_template_value_is_escaped_with_rdn_rules(directory: MockDirectory) -> None:
    hostile = cast("LoginId", SimpleNamespace(value="x,ou=admins+cn=y"))

    with pytest.raises(InvalidCredentialsError):
        await make_adapter(directory).authenticate(
            make_directory_settings(),
            hostile,
            Password(PASSWORD),
        )

    bind_user = directory.factory_calls[0][1]
    assert bind_user == r"cn=x\,ou\=admins\+cn\=y,ou=users,dc=corp,dc=test"


async def test_search_with_no_match_is_misconfigured_at_search(directory: MockDirectory) -> None:
    error = await failure(
        directory, user_filter="(&(objectClass=user)(sAMAccountName=zz{login_id}))"
    )

    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SEARCH
    assert isinstance(error, DirectoryUnavailableError)


async def test_search_with_several_matches_is_misconfigured_at_search(
    directory: MockDirectory,
) -> None:
    directory.add_user("dup", PASSWORD)
    directory.add_entry("cn=dup2,ou=staff,dc=corp,dc=test", user_attributes("dup", PASSWORD))

    error = await failure(directory, login_id="dup")

    assert isinstance(error, DirectoryMisconfiguredError)
    assert error.stage is VerificationStage.SEARCH


async def test_search_uses_the_configured_base_dn_and_limits_results(
    directory: MockDirectory,
) -> None:
    await login(directory)

    search = directory.connections[-1].search_args[-1]
    assert search["search_base"] == "dc=corp,dc=test"
    assert search["size_limit"] == 2
    attributes = search["attributes"]
    assert isinstance(attributes, list)
    assert set(attributes) >= {"displayName", "mail"}
