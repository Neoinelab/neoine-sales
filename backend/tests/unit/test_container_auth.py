"""조립(Container)의 인증 계약: OIDC 조립은 없고 디렉터리 로그인·최초 설정 유스케이스가 있다."""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from app.application.auth.auth_status import GetAuthStatus
from app.application.auth.directory_login import DirectoryLogin
from app.application.auth.setup_directory import RegisterSetupDirectory
from app.application.auth.setup_first_admin import SetupFirstAdmin

from app.application.auth.authenticate import Authenticate
from app.container import Container
from app.infra.auth.ldap import LdapDirectoryAuthenticator
from tests.e2e.conftest import make_settings
from tests.fakes.directory import FakeDirectoryAuthenticator

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest_asyncio.fixture
async def container() -> AsyncIterator[Container]:
    built = Container(make_settings())  # 엔진만 만들 뿐 DB에는 접속하지 않는다
    yield built
    await built.dispose()


async def test_container_builds_the_auth_use_cases_without_any_oidc_settings(
    container: Container,
) -> None:
    assert isinstance(container.auth_status(), GetAuthStatus)
    assert isinstance(container.register_setup_directory(), RegisterSetupDirectory)
    assert isinstance(container.setup_first_admin(), SetupFirstAdmin)
    assert isinstance(container.directory_login(), DirectoryLogin)
    assert isinstance(container.authenticate(), Authenticate)


@pytest.mark.parametrize("removed", ["begin_login", "complete_login"])
async def test_container_no_longer_exposes_oidc_use_cases(
    container: Container, removed: str
) -> None:
    assert not hasattr(container, removed)


async def test_container_accepts_an_injected_directory_authenticator() -> None:
    built = Container(make_settings(), directory=FakeDirectoryAuthenticator())
    try:
        assert isinstance(built.directory_login(), DirectoryLogin)
    finally:
        await built.dispose()


async def test_container_uses_the_ldap_adapter_by_default(container: Container) -> None:
    assert isinstance(container.directory, LdapDirectoryAuthenticator)
