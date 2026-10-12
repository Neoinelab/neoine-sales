"""DirectoryAuthenticator 계약: Fake와 ldap3 어댑터(MOCK_SYNC)에 같은 테스트를 적용한다.

호출자(유스케이스)가 기대하는 공통 의미만 고정한다: 성공 시 DirectoryUser, 잘못된 계정·비밀번호는
InvalidCredentialsError(BIND), probe는 성공하면 None.
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
from tests.factories_auth import make_directory_settings
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
    return Harness(LdapDirectoryAuthenticator(mock.factory))


@pytest.fixture(params=[pytest.param(_fake, id="fake"), pytest.param(_ldap, id="ldap3-mock")])
def harness(request: pytest.FixtureRequest) -> Harness:
    return request.param()  # type: ignore[no-any-return]


async def test_valid_credentials_return_the_directory_user(harness: Harness) -> None:
    user = await harness.authenticator.authenticate(
        make_directory_settings(), LoginId("kim"), Password(PASSWORD)
    )

    assert user == DirectoryUser(login_id="kim", display_name="김영업", email="kim@corp.test")


async def test_wrong_password_is_rejected_at_bind(harness: Harness) -> None:
    with pytest.raises(InvalidCredentialsError) as caught:
        await harness.authenticator.authenticate(
            make_directory_settings(), LoginId("kim"), Password("Wrong-password-1")
        )

    assert caught.value.stage is VerificationStage.BIND


async def test_unknown_account_is_rejected_at_bind(harness: Harness) -> None:
    with pytest.raises(InvalidCredentialsError) as caught:
        await harness.authenticator.authenticate(
            make_directory_settings(), LoginId("nobody"), Password(PASSWORD)
        )

    assert caught.value.stage is VerificationStage.BIND


async def test_probe_succeeds_without_credentials(harness: Harness) -> None:
    await harness.authenticator.probe(make_directory_settings())  # 예외가 없으면 성공이다
