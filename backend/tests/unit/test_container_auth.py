"""조립(Container)의 인증 계약: OIDC 조립은 없고 디렉터리 로그인·최초 설정 유스케이스가 있다."""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.application.auth.auth_status import GetAuthStatus
from app.application.auth.authenticate import Authenticate
from app.application.auth.dev_login import DevLogin
from app.application.auth.directory_login import DirectoryLogin
from app.application.auth.setup_directory import RegisterSetupDirectory
from app.application.auth.setup_first_admin import SetupFirstAdmin
from app.application.user.delete_user import DeleteUser
from app.application.user.list_user_options import ListUserOptions
from app.application.user.resolve_user_refs import ResolveUserRefs
from app.container import Container
from app.infra.auth.ldap import LdapDirectoryAuthenticator
from tests.fakes.directory import FakeDirectoryAuthenticator
from tests.functional.conftest import make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


@pytest_asyncio.fixture
async def container() -> AsyncIterator[Container]:
    built = Container(make_settings(UNUSED_DATABASE_URL))  # 엔진만 만들 뿐 DB에는 접속하지 않는다
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


async def test_container_builds_the_user_fk_use_cases(container: Container) -> None:
    assert isinstance(container.delete_user(), DeleteUser)
    assert isinstance(container.list_user_options(), ListUserOptions)
    assert isinstance(container.resolve_user_refs(), ResolveUserRefs)
    assert isinstance(container.dev_login(), DevLogin)


@pytest.mark.parametrize("removed", ["begin_login", "complete_login"])
async def test_container_no_longer_exposes_oidc_use_cases(
    container: Container, removed: str
) -> None:
    assert not hasattr(container, removed)


async def test_container_accepts_an_injected_directory_authenticator() -> None:
    built = Container(make_settings(UNUSED_DATABASE_URL), directory=FakeDirectoryAuthenticator())
    try:
        assert isinstance(built.directory_login(), DirectoryLogin)
    finally:
        await built.dispose()


async def test_container_uses_the_ldap_adapter_by_default(container: Container) -> None:
    assert isinstance(container.directory, LdapDirectoryAuthenticator)


async def test_container_builds_the_cipher_from_the_configured_key_and_the_scrypt_hasher(
    container: Container,
) -> None:
    from app.infra.crypto.fernet_cipher import FernetSecretCipher  # noqa: PLC0415
    from app.infra.crypto.scrypt_hasher import ScryptPasswordHasher  # noqa: PLC0415

    from tests.support.crypto_keys import OTHER_FERNET_KEY, TEST_FERNET_KEY  # noqa: PLC0415

    assert isinstance(container.cipher, FernetSecretCipher)
    assert isinstance(container.password_hasher, ScryptPasswordHasher)
    sealed = container.cipher.seal("Dummy-bind-pw-1!")
    assert container.cipher.unseal(sealed) == "Dummy-bind-pw-1!"
    other = Container(make_settings(UNUSED_DATABASE_URL, settings_encryption_key=OTHER_FERNET_KEY))
    try:
        assert TEST_FERNET_KEY != OTHER_FERNET_KEY
        with pytest.raises(Exception, match=r"."):
            other.cipher.unseal(sealed)
    finally:
        await other.dispose()


async def test_container_accepts_an_injected_cipher_and_hasher() -> None:
    from tests.fakes.password_hasher import FakePasswordHasher  # noqa: PLC0415
    from tests.fakes.secret_cipher import FakeSecretCipher  # noqa: PLC0415

    cipher, hasher = FakeSecretCipher(), FakePasswordHasher()
    built = Container(make_settings(UNUSED_DATABASE_URL), cipher=cipher, password_hasher=hasher)
    try:
        assert built.cipher is cipher
        assert built.password_hasher is hasher
        assert isinstance(built.directory_login(), DirectoryLogin)
    finally:
        await built.dispose()
