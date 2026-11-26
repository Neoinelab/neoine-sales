from typing import TYPE_CHECKING

from app.domain.auth.credentials import LoginId, Password
from app.infra.auth.ldap import LdapDirectoryAuthenticator
from tests.factories_auth import BASE_DN, BIND_PASSWORD
from tests.factories_directory import make_directory_settings
from tests.support.ldap_adapter import PASSWORD

if TYPE_CHECKING:
    from tests.support.ldap_mock import MockDirectory


async def test_short_test_account_gets_the_domain_before_binding(directory: MockDirectory) -> None:
    """임시 테스트 계정에는 AD 도메인을 자동으로 붙여 바인드한다."""
    # given: 짧은 계정과 도메인 바인드를 허용하는 AD
    directory.upn_passwords["operator@corp.test"] = BIND_PASSWORD
    adapter = LdapDirectoryAuthenticator(directory.factory, user_bind_domain="corp.test")

    # when: 연결 테스트를 수행한다
    base_dn = await adapter.discover_base_dn(make_directory_settings(bind_account="operator"))

    # then: UPN으로 연결하고 Base DN을 찾는다
    assert base_dn == BASE_DN
    assert [user for _, user, _ in directory.factory_calls] == ["operator@corp.test"]


async def test_login_binds_as_the_user_without_a_saved_service_account(
    directory: MockDirectory,
) -> None:
    """로그인 사용자의 UPN으로 한 번 바인드하고 같은 연결에서 프로필을 조회한다."""
    # given: 로그인 계정의 UPN과 비밀번호가 유효하다
    directory.upn_passwords["kim@corp.test"] = PASSWORD
    adapter = LdapDirectoryAuthenticator(directory.factory, user_bind_domain="corp.test")

    # when: 사용자가 로그인한다
    user = await adapter.authenticate(
        make_directory_settings(), BASE_DN, LoginId("kim"), Password(PASSWORD)
    )

    # then: 저장된 서비스 계정으로 연결하지 않고 사용자 프로필을 얻는다
    assert user.login_id == "kim"
    assert [(account, secret) for _, account, secret in directory.factory_calls] == [
        ("kim@corp.test", PASSWORD)
    ]
    assert len(directory.connections[0].search_args) == 1
