"""대체 로그인 경고 단계와 안내 문구(AC14·AC15): warning_stage_of, FALLBACK_MESSAGES."""

import pytest
from app.application.auth.fallback_login import (
    DirectoryWarning,
    DirectoryWarningStage,
    warning_stage_of,
)

from app.application.auth.messages import FALLBACK_MESSAGES
from app.application.directory.errors import DirectoryCredentialUnreadableError
from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)

STAGE_VALUES = [
    "not_configured",
    "connect",
    "tls",
    "service_bind",
    "base_dn",
    "search",
    "credential_unreadable",
    "unknown",
]


def test_warning_stages_have_the_documented_values() -> None:
    assert [stage.value for stage in DirectoryWarningStage] == STAGE_VALUES


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        (VerificationStage.CONNECT, DirectoryWarningStage.CONNECT),
        (VerificationStage.TLS, DirectoryWarningStage.TLS),
        (VerificationStage.SERVICE_BIND, DirectoryWarningStage.SERVICE_BIND),
        (VerificationStage.BASE_DN, DirectoryWarningStage.BASE_DN),
        (VerificationStage.SEARCH, DirectoryWarningStage.SEARCH),
        (VerificationStage.BIND, DirectoryWarningStage.UNKNOWN),
        (None, DirectoryWarningStage.UNKNOWN),
    ],
)
def test_warning_stage_follows_the_directory_error_stage(
    stage: VerificationStage | None, expected: DirectoryWarningStage
) -> None:
    assert warning_stage_of(DirectoryUnavailableError(stage=stage)) is expected
    assert warning_stage_of(DirectoryMisconfiguredError(stage=stage)) is expected


def test_unreadable_credential_error_is_its_own_stage() -> None:
    assert (
        warning_stage_of(DirectoryCredentialUnreadableError())
        is DirectoryWarningStage.CREDENTIAL_UNREADABLE
    )


def test_credential_unreadable_error_is_a_directory_unavailable_error_without_secrets() -> None:
    error = DirectoryCredentialUnreadableError()

    assert isinstance(error, DirectoryUnavailableError)
    assert str(error)
    assert not isinstance(error, InvalidCredentialsError)


def test_every_stage_has_a_distinct_popup_message() -> None:
    assert set(FALLBACK_MESSAGES) == set(DirectoryWarningStage)
    messages = [FALLBACK_MESSAGES[stage] for stage in DirectoryWarningStage]
    assert len(set(messages)) == len(messages)
    for message in messages:
        assert "이전에 로그인한 비밀번호로 로그인했습니다" in message


def test_messages_point_to_what_the_admin_should_check() -> None:
    assert "Admin > 외부연동" in FALLBACK_MESSAGES[DirectoryWarningStage.NOT_CONFIGURED]
    assert "바인드 계정" in FALLBACK_MESSAGES[DirectoryWarningStage.SERVICE_BIND]
    assert "사용자 필터" in FALLBACK_MESSAGES[DirectoryWarningStage.SEARCH]
    assert "암호화 키" in FALLBACK_MESSAGES[DirectoryWarningStage.CREDENTIAL_UNREADABLE]


def test_directory_warning_carries_stage_and_message() -> None:
    warning = DirectoryWarning(
        stage=DirectoryWarningStage.CONNECT,
        message=FALLBACK_MESSAGES[DirectoryWarningStage.CONNECT],
    )

    assert (warning.stage, warning.message) == (
        DirectoryWarningStage.CONNECT,
        FALLBACK_MESSAGES[DirectoryWarningStage.CONNECT],
    )
