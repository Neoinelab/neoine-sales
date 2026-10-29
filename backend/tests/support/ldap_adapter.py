"""ldap3 어댑터 테스트 공통 도우미.

`unit/infra/conftest.py`가 이 모듈을 가져오므로 새 도메인 모듈(factories_directory)은 사용 시점에
가져온다(구현 전에도 같은 디렉터리의 다른 infra 테스트가 수집된다).
"""

from typing import TYPE_CHECKING, Any

import pytest

from app.application.ports.directory import DirectoryError, DirectoryUser
from app.domain.auth.credentials import LoginId, Password
from app.infra.auth.ldap import LdapDirectoryAuthenticator
from tests.factories_auth import BASE_DN

if TYPE_CHECKING:
    from tests.support.ldap_mock import MockDirectory

PASSWORD = "Correct-Horse-1"  # noqa: S105 - 테스트용 더미 값


def make_adapter(directory: MockDirectory) -> LdapDirectoryAuthenticator:
    return LdapDirectoryAuthenticator(directory.factory)


async def login(
    directory: MockDirectory,
    login_id: str = "kim",
    attempt: str = PASSWORD,
    *,
    base_dn: str = BASE_DN,
    **overrides: Any,  # noqa: ANN401
) -> DirectoryUser:
    """서비스 계정 search-then-bind로 로그인한다. overrides는 접속 정보(필터 등)를 바꾼다."""
    from tests.factories_directory import make_directory_settings  # noqa: PLC0415

    return await make_adapter(directory).authenticate(
        make_directory_settings(**overrides), base_dn, LoginId(login_id), Password(attempt)
    )


async def failure(
    directory: MockDirectory,
    login_id: str = "kim",
    attempt: str = PASSWORD,
    *,
    base_dn: str = BASE_DN,
    **overrides: Any,  # noqa: ANN401
) -> DirectoryError:
    with pytest.raises(DirectoryError) as caught:
        await login(directory, login_id, attempt, base_dn=base_dn, **overrides)
    return caught.value


async def discover(directory: MockDirectory, **overrides: Any) -> str:  # noqa: ANN401
    from tests.factories_directory import make_directory_settings  # noqa: PLC0415

    return await make_adapter(directory).discover_base_dn(make_directory_settings(**overrides))


async def discovery_failure(directory: MockDirectory, **overrides: Any) -> DirectoryError:  # noqa: ANN401
    with pytest.raises(DirectoryError) as caught:
        await discover(directory, **overrides)
    return caught.value
