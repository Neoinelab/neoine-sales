"""조립(Container)의 인증 계약: OIDC 조립은 없고 디렉터리 로그인·최초 설정 유스케이스가 있다."""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.application.auth.auth_status import GetAuthStatus
from app.application.auth.authenticate import Authenticate
from app.application.auth.directory_login import DirectoryLogin
from app.application.auth.setup_directory import RegisterSetupDirectory
from app.application.auth.setup_first_admin import SetupFirstAdmin
from app.application.user.delete_user import DeleteUser
from app.application.user.list_user_options import ListUserOptions
from app.application.user.resolve_user_refs import ResolveUserRefs
from app.container import Container
from app.infra.auth.ldap import LdapDirectoryAuthenticator
from tests.fakes.directory import FakeDirectoryAuthenticator
from tests.support.app_settings import make_settings

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
    """OIDC 설정 없이도 인증 유스케이스를 조립한다."""
    # when: 인증 유스케이스를 조립한다 (전제: container)
    result = container.auth_status()
    # then: 각 인증 유스케이스 종류다
    assert isinstance(result, GetAuthStatus)
    assert isinstance(container.register_setup_directory(), RegisterSetupDirectory)
    assert isinstance(container.setup_first_admin(), SetupFirstAdmin)
    assert isinstance(container.directory_login(), DirectoryLogin)
    assert isinstance(container.authenticate(), Authenticate)


async def test_container_builds_the_user_fk_use_cases(container: Container) -> None:
    """사용자 FK 관련 유스케이스를 조립하고 개발 로그인은 없다."""
    # when: 사용자 삭제 유스케이스를 조립한다 (전제: container)
    result = container.delete_user()
    # then: DeleteUser 종류다
    assert isinstance(result, DeleteUser)
    assert isinstance(container.list_user_options(), ListUserOptions)
    assert isinstance(container.resolve_user_refs(), ResolveUserRefs)
    assert not hasattr(container, "dev_login")


@pytest.mark.parametrize("removed", ["begin_login", "complete_login"])
async def test_container_no_longer_exposes_oidc_use_cases(
    container: Container, removed: str
) -> None:
    """OIDC 유스케이스는 더 이상 노출하지 않는다."""
    # when: 폐지된 OIDC 유스케이스 이름이 있는지 본다 (전제: container)
    exposed = hasattr(container, removed)

    # then: 없다
    assert not exposed


async def test_container_accepts_an_injected_directory_authenticator() -> None:
    """주입한 디렉터리 인증기로 조립할 수 있다."""
    # given: Fake 디렉터리 인증기를 주입한 컨테이너
    built = Container(make_settings(UNUSED_DATABASE_URL), directory=FakeDirectoryAuthenticator())
    # when·then: 디렉터리 로그인 유스케이스를 조립할 수 있다
    try:
        assert isinstance(built.directory_login(), DirectoryLogin)
    finally:
        await built.dispose()


async def test_container_uses_the_ldap_adapter_by_default(container: Container) -> None:
    """주입하지 않으면 LDAP 어댑터를 쓴다."""
    # when·then: 기본 디렉터리 인증기가 LDAP 어댑터다 (전제: container)
    assert isinstance(container.directory, LdapDirectoryAuthenticator)


async def test_container_builds_the_cipher_from_the_configured_key_and_the_scrypt_hasher(
    container: Container,
) -> None:
    """설정한 키로 암호기를, scrypt로 해시기를 조립한다."""
    from app.infra.crypto.fernet_cipher import FernetSecretCipher  # noqa: PLC0415
    from app.infra.crypto.scrypt_hasher import ScryptPasswordHasher  # noqa: PLC0415
    from tests.support.crypto_keys import OTHER_FERNET_KEY, TEST_FERNET_KEY  # noqa: PLC0415

    # when·then: 암호기는 Fernet 구현이고 해시기는 scrypt 구현이다 (전제: container)
    assert isinstance(container.cipher, FernetSecretCipher)
    assert isinstance(container.password_hasher, ScryptPasswordHasher)
    # when: 비밀을 봉인하고 같은 키로 푼다
    sealed = container.cipher.seal("Dummy-bind-pw-1!")
    restored = container.cipher.unseal(sealed)
    # then: 원래 값으로 복원된다
    assert restored == "Dummy-bind-pw-1!"
    # given: 다른 키로 조립한 컨테이너
    other = Container(make_settings(UNUSED_DATABASE_URL, settings_encryption_key=OTHER_FERNET_KEY))
    # when·then: 다른 키로는 봉인한 값을 풀 수 없다
    try:
        assert TEST_FERNET_KEY != OTHER_FERNET_KEY
        with pytest.raises(Exception, match=r"."):
            other.cipher.unseal(sealed)
    finally:
        await other.dispose()


async def test_container_accepts_an_injected_cipher_and_hasher() -> None:
    """주입한 암호기와 해시기를 그대로 쓴다."""
    from tests.fakes.password_hasher import FakePasswordHasher  # noqa: PLC0415
    from tests.fakes.secret_cipher import FakeSecretCipher  # noqa: PLC0415

    # given: Fake 암호기와 해시기를 주입한 컨테이너
    cipher, hasher = FakeSecretCipher(), FakePasswordHasher()
    built = Container(make_settings(UNUSED_DATABASE_URL), cipher=cipher, password_hasher=hasher)
    # when·then: 컨테이너가 주입한 객체를 쓰고 로그인 유스케이스를 조립한다
    try:
        assert built.cipher is cipher
        assert built.password_hasher is hasher
        assert isinstance(built.directory_login(), DirectoryLogin)
    finally:
        await built.dispose()


@pytest.mark.parametrize("domain", ["neoine.co.kr", None])
async def test_container_builds_the_ldap_adapter_with_the_configured_login_domain(
    domain: str | None,
) -> None:
    """조립한 LDAP 어댑터는 설정의 도메인을 쓰고 로그인·AD 확인·첫 admin 등록이 공유한다.

    테스트 코드: AU-099
    """
    # given: ad_login_domain이 있는(또는 없는) 설정
    built = Container(make_settings(UNUSED_DATABASE_URL, ad_login_domain=domain))

    try:
        # when: 디렉터리를 주입하지 않고 조립한다
        directory = built.directory

        # then: 설정의 도메인을 쓰는 LDAP 어댑터이고 세 유스케이스가 같은 객체를 받는다
        assert isinstance(directory, LdapDirectoryAuthenticator)
        assert directory.user_bind_domain == domain
        assert built.directory_login()._deps.directory is directory
        assert built.setup_first_admin()._deps.directory is directory
        assert built.test_directory_settings()._verify._directory is directory
    finally:
        await built.dispose()
