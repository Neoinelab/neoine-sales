"""FakeDirectoryAuthenticator 자체의 동작(다른 유스케이스 테스트가 의존한다)."""

import pytest

from app.application.ports.directory import (
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.auth.credentials import LoginId, Password
from tests.factories_auth import BASE_DN
from tests.factories_directory import make_directory_settings
from tests.fakes.directory import FakeDirectoryAuthenticator


async def test_fake_records_calls_and_returns_registered_account() -> None:
    """Fake는 호출을 기록하고 등록한 계정을 돌려준다."""
    # given: 계정이 등록된 Fake 디렉터리
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", "pw-1", display_name="김영업", email="kim@corp.test")
    settings = make_directory_settings()

    # when: 등록한 계정으로 인증한다
    user = await fake.authenticate(settings, BASE_DN, LoginId("kim"), Password("pw-1"))

    # then: 계정 정보를 돌려주고 호출 인자가 기록된다
    assert user.display_name == "김영업"
    assert len(fake.authenticate_calls) == 1
    call = fake.authenticate_calls[0]
    assert (call.settings, call.base_dn, call.login_id, call.password) == (
        settings,
        BASE_DN,
        LoginId("kim"),
        "pw-1",
    )


async def test_fake_authenticate_failure_override_wins_over_account_lookup() -> None:
    """실패 지정이 계정 조회보다 우선하고 실패한 호출도 기록한다."""
    # given: 연결 실패가 지정된 Fake
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", "pw-1")
    fake.authenticate_fails_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)

    # when·then: 등록된 계정으로 인증해도 DirectoryUnavailableError가 난다
    with pytest.raises(DirectoryUnavailableError):
        await fake.authenticate(
            make_directory_settings(), BASE_DN, LoginId("kim"), Password("pw-1")
        )

    # then: 실패한 호출도 기록된다
    assert len(fake.authenticate_calls) == 1  # 실패한 호출도 기록한다


async def test_fake_rejects_unknown_account_at_search_and_wrong_password_at_bind() -> None:
    """없는 계정은 검색 단계, 틀린 비밀번호는 바인드 단계에서 거부한다."""
    # given: 계정 kim이 등록된 Fake
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", "pw-1")

    # when·then: 없는 계정·틀린 비밀번호로 인증하면 해당 단계의 InvalidCredentialsError다
    for login, password, stage in (
        ("lee", "pw-1", VerificationStage.SEARCH),
        ("kim", "other", VerificationStage.BIND),
    ):
        with pytest.raises(InvalidCredentialsError) as caught:
            await fake.authenticate(
                make_directory_settings(), BASE_DN, LoginId(login), Password(password)
            )
        assert caught.value.stage is stage


async def test_fake_discover_returns_the_configured_base_dn_and_records_settings() -> None:
    """Base DN 탐색은 지정한 값을 돌려주고 설정을 기록하며 실패 지정도 따른다."""
    # given: Base DN이 지정된 Fake
    fake = FakeDirectoryAuthenticator()
    fake.base_dn = "dc=other,dc=test"
    settings = make_directory_settings()

    # when: 탐색한다
    result = await fake.discover_base_dn(settings)
    # then: 지정한 Base DN을 돌려준다
    assert result == "dc=other,dc=test"
    # given: TLS 실패 지정
    fake.discover_fails_with = DirectoryUnavailableError(stage=VerificationStage.TLS)
    # when·then: 다시 탐색하면 DirectoryUnavailableError가 난다
    with pytest.raises(DirectoryUnavailableError):
        await fake.discover_base_dn(settings)

    # then: 두 번의 호출 설정이 기록된다
    assert fake.discover_calls == [settings, settings]


async def test_fake_fail_all_with_breaks_both_operations_and_none_restores_them() -> None:
    """fail_all_with는 두 동작을 모두 실패시키고 None으로 되돌린다."""
    # given: 계정이 등록되고 전체 실패가 지정된 Fake
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", "pw-1")
    settings = make_directory_settings()
    fake.fail_all_with(DirectoryUnavailableError(stage=VerificationStage.CONNECT))

    # when·then: 탐색은 DirectoryUnavailableError가 난다
    # when·then: 인증도 DirectoryUnavailableError가 난다
    with pytest.raises(DirectoryUnavailableError):
        await fake.discover_base_dn(settings)
    with pytest.raises(DirectoryUnavailableError):
        await fake.authenticate(settings, BASE_DN, LoginId("kim"), Password("pw-1"))
    # when: 전체 실패 지정을 해제한다
    fake.fail_all_with(None)

    # then: 탐색과 인증이 다시 정상 동작한다
    assert await fake.discover_base_dn(settings) == BASE_DN
    assert (
        await fake.authenticate(settings, BASE_DN, LoginId("kim"), Password("pw-1"))
    ).login_id == "kim"
