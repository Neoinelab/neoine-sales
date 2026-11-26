"""DirectoryAuthenticator 계약: Fake와 ldap3 어댑터(MOCK_SYNC)에 같은 테스트를 적용한다.

호출자(유스케이스)가 기대하는 공통 의미만 고정한다: 성공 시 DirectoryUser, 사용자를 못 찾으면
InvalidCredentialsError(SEARCH), 비밀번호가 틀리면 InvalidCredentialsError(BIND), Base DN 탐색은
문자열을 돌려준다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from app.application.ports.directory import (
    DirectoryUser,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.auth.credentials import LoginId, Password
from app.infra.auth.ldap import LdapDirectoryAuthenticator
from tests.factories_auth import BASE_DN
from tests.factories_directory import make_directory_settings
from tests.fakes.directory import FakeDirectoryAuthenticator
from tests.support.ldap_mock import MockDirectory

if TYPE_CHECKING:
    from app.application.ports.directory import DirectoryAuthenticator

PASSWORD = "Correct-Horse-1"  # noqa: S105 - 테스트용 더미 값


@dataclass
class Harness:
    authenticator: DirectoryAuthenticator


def _fake() -> Harness:
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", PASSWORD, display_name="김영업", email="kim@corp.test")
    return Harness(fake)


def _ldap() -> Harness:
    mock = MockDirectory()
    mock.add_user("kim", PASSWORD, display_name="김영업", mail="kim@corp.test")
    return Harness(LdapDirectoryAuthenticator(mock.factory, user_bind_domain="corp.test"))


@pytest.fixture(params=[pytest.param(_fake, id="fake"), pytest.param(_ldap, id="ldap3-mock")])
def harness(request: pytest.FixtureRequest) -> Harness:
    return request.param()  # type: ignore[no-any-return]


async def test_valid_credentials_return_the_directory_user(harness: Harness) -> None:
    """올바른 자격 증명이면 DirectoryUser를 돌려준다."""
    # when: 올바른 자격 증명으로 인증한다 (전제: harness에 kim 계정이 있다)
    user = await harness.authenticator.authenticate(
        make_directory_settings(), BASE_DN, LoginId("kim"), Password(PASSWORD)
    )

    # then: 계정의 아이디·표시 이름·이메일이다
    assert user == DirectoryUser(login_id="kim", display_name="김영업", email="kim@corp.test")


async def test_wrong_password_is_rejected_at_bind(harness: Harness) -> None:
    """비밀번호가 틀리면 바인드 단계의 자격 증명 오류다."""
    # when: 틀린 비밀번호로 인증한다 (전제: harness에 kim 계정이 있다)
    with pytest.raises(InvalidCredentialsError) as caught:
        await harness.authenticator.authenticate(
            make_directory_settings(), BASE_DN, LoginId("kim"), Password("Wrong-password-1")
        )

    # then: BIND 단계의 오류다
    assert caught.value.stage is VerificationStage.BIND


async def test_unknown_account_is_rejected_at_search(harness: Harness) -> None:
    """없는 계정은 검색 단계의 자격 증명 오류다."""
    # when: 없는 아이디로 인증한다 (전제: harness에 kim 계정만 있다)
    with pytest.raises(InvalidCredentialsError) as caught:
        await harness.authenticator.authenticate(
            make_directory_settings(), BASE_DN, LoginId("nobody"), Password(PASSWORD)
        )

    # then: SEARCH 단계의 오류다
    assert caught.value.stage in {VerificationStage.BIND, VerificationStage.SEARCH}


async def test_discover_base_dn_returns_the_naming_context(harness: Harness) -> None:
    """Base DN 탐색은 디렉터리의 naming context 문자열을 돌려준다."""
    # when: Base DN을 탐색한다 (전제: harness가 디렉터리를 흉내 낸다)
    found = await harness.authenticator.discover_base_dn(make_directory_settings())

    # then: 흉내 낸 디렉터리의 naming context(BASE_DN)와 같다
    assert found == BASE_DN
