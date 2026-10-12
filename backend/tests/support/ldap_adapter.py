"""ldap3 어댑터 테스트 공통 도우미."""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.directory import DirectoryError, DirectoryUser
from app.domain.auth.credentials import LoginId, Password
from app.infra.auth.ldap import LdapDirectoryAuthenticator
from tests.factories_auth import make_directory_settings

if TYPE_CHECKING:
    from tests.support.ldap_mock import MockDirectory

PASSWORD = "Correct-Horse-1"  # noqa: S105 - 테스트용 더미 값


def make_adapter(directory: MockDirectory) -> LdapDirectoryAuthenticator:
    return LdapDirectoryAuthenticator(directory.factory)


async def login(
    directory: MockDirectory, login_id: str = "kim", attempt: str = PASSWORD, **overrides: object
) -> DirectoryUser:
    return await make_adapter(directory).authenticate(
        make_directory_settings(**overrides), LoginId(login_id), Password(attempt)
    )


async def failure(
    directory: MockDirectory, login_id: str = "kim", attempt: str = PASSWORD, **overrides: object
) -> DirectoryError:
    with pytest.raises(DirectoryError) as caught:
        await login(directory, login_id, attempt, **overrides)
    return caught.value
