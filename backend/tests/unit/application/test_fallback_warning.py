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
    """경고 단계 값은 문서의 여덟 가지다.

    테스트 코드: AU-023
    """
    # when: 경고 단계 값을 나열하면
    actual = [stage.value for stage in DirectoryWarningStage]
    # then: 문서의 여덟 값과 순서가 같다
    assert actual == STAGE_VALUES


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
    """AD 오류의 단계가 경고 단계로 옮겨진다.

    테스트 코드: AU-023
    """
    # when: AD 불가·설정 오류의 단계를 경고 단계로 바꾸면
    actual = warning_stage_of(DirectoryUnavailableError(stage=stage))
    # then: 단계 없는 통신 실패와 사용자 바인드 단계는 unknown이다
    assert actual is expected
    assert warning_stage_of(DirectoryMisconfiguredError(stage=stage)) is expected


def test_unreadable_credential_error_is_its_own_stage() -> None:
    """바인드 비밀번호 복호화 실패는 고유한 경고 단계다.

    테스트 코드: AU-023
    """
    # when: 복호화 실패 오류의 경고 단계를 구하면
    actual = warning_stage_of(DirectoryCredentialUnreadableError())
    # then: credential_unreadable이다
    assert actual is DirectoryWarningStage.CREDENTIAL_UNREADABLE


def test_credential_unreadable_error_is_a_directory_unavailable_error_without_secrets() -> None:
    """복호화 실패 오류는 비밀 없이 AD 불가 오류의 한 종류다."""
    # when: 복호화 실패 오류를 만들면
    error = DirectoryCredentialUnreadableError()

    # then: AD 불가 오류이고 문구가 있으며 자격증명 거절 오류가 아니다
    assert isinstance(error, DirectoryUnavailableError)
    assert str(error)
    assert not isinstance(error, InvalidCredentialsError)


def test_every_stage_has_a_distinct_popup_message() -> None:
    """단계마다 서로 다른 안내 문구가 있다.

    테스트 코드: AU-023
    """
    # when: 단계별 안내 문구를 모으면
    assert set(FALLBACK_MESSAGES) == set(DirectoryWarningStage)
    # then: 모든 단계에 문구가 있고 서로 다르며 공통 안내를 담는다
    messages = [FALLBACK_MESSAGES[stage] for stage in DirectoryWarningStage]
    assert len(set(messages)) == len(messages)
    for message in messages:
        assert "이전에 로그인한 비밀번호로 로그인했습니다" in message


def test_messages_point_to_what_the_admin_should_check() -> None:
    """안내 문구는 admin이 확인할 곳을 가리킨다.

    테스트 코드: AU-023
    """
    # when: 주요 단계의 문구를 보면
    actual = FALLBACK_MESSAGES[DirectoryWarningStage.NOT_CONFIGURED]
    # then: 외부연동·바인드 계정·사용자 필터·암호화 키를 안내한다
    assert "Admin > 외부연동" in actual
    assert "바인드 계정" in FALLBACK_MESSAGES[DirectoryWarningStage.SERVICE_BIND]
    assert "사용자 필터" in FALLBACK_MESSAGES[DirectoryWarningStage.SEARCH]
    assert "암호화 키" in FALLBACK_MESSAGES[DirectoryWarningStage.CREDENTIAL_UNREADABLE]


def test_directory_warning_carries_stage_and_message() -> None:
    """경고 값 객체는 단계와 문구를 담는다."""
    # when: 단계와 문구로 경고를 만들면
    warning = DirectoryWarning(
        stage=DirectoryWarningStage.CONNECT,
        message=FALLBACK_MESSAGES[DirectoryWarningStage.CONNECT],
    )

    # then: 단계와 문구가 그대로 있다
    assert (warning.stage, warning.message) == (
        DirectoryWarningStage.CONNECT,
        FALLBACK_MESSAGES[DirectoryWarningStage.CONNECT],
    )


def test_fallback_messages_match_the_documented_texts() -> None:
    """admin 경고 문구는 문서의 단계별 문구와 정확히 같다.

    테스트 코드: AU-023
    """
    # when: 단계별 안내 문구를 읽으면
    messages = {stage.value: text for stage, text in FALLBACK_MESSAGES.items()}

    # then: 문서 2.8의 문구와 같다
    assert messages == {
        "not_configured": (
            "AD 설정이 없어 이전에 로그인한 비밀번호로 로그인했습니다. "
            "Admin > 외부연동에서 AD 설정을 등록하세요."
        ),
        "connect": (
            "AD 서버에 연결하지 못해 이전에 로그인한 비밀번호로 로그인했습니다. "
            "호스트·포트·방화벽을 확인하세요."
        ),
        "tls": (
            "AD 보안 연결(SSL/StartTLS)을 맺지 못해 이전에 로그인한 비밀번호로 로그인했습니다. "
            "보안 연결 방식과 포트를 확인하세요."
        ),
        "service_bind": (
            "바인드 계정으로 AD에 로그인하지 못해 이전에 로그인한 비밀번호로 로그인했습니다. "
            "바인드 계정과 비밀번호를 확인하세요."
        ),
        "base_dn": (
            "AD 검색 기준(Base DN)으로 사용자를 찾지 못해 "
            "이전에 로그인한 비밀번호로 로그인했습니다. AD 설정을 다시 저장하세요."
        ),
        "search": (
            "사용자 필터에 맞는 AD 사용자가 둘 이상이라 이전에 로그인한 비밀번호로 로그인했습니다. "
            "사용자 필터를 확인하세요."
        ),
        "credential_unreadable": (
            "저장된 바인드 비밀번호를 읽을 수 없어(암호화 키 변경 여부 확인) "
            "이전에 로그인한 비밀번호로 로그인했습니다. "
            "외부연동에서 바인드 비밀번호를 다시 입력하세요."
        ),
        "unknown": (
            "AD 서버와 통신하지 못해 이전에 로그인한 비밀번호로 로그인했습니다. "
            "AD 설정과 서버 상태를 확인하세요."
        ),
    }
