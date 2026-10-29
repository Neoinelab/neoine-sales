"""ldap3·소켓·TLS 예외를 디렉터리 Port의 오류와 단계로 바꾼다. 원인 상세는 메시지에 싣지 않는다."""

import ssl

from ldap3.core.exceptions import (
    LDAPSSLConfigurationError,
    LDAPSSLNotSupportedError,
    LDAPStartTLSError,
)

from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)

# LDAP 결과 코드: 49 invalidCredentials, 50 insufficientAccessRights, 53 unwillingToPerform
CREDENTIAL_REJECTION_CODES = frozenset({49, 50, 53})

MESSAGES = {
    VerificationStage.CONNECT: "디렉터리 서버에 연결하지 못했습니다",
    VerificationStage.TLS: "디렉터리 서버와 TLS 연결을 맺지 못했습니다",
    VerificationStage.SERVICE_BIND: "디렉터리 서버가 서비스 계정 바인드를 처리하지 못했습니다",
    VerificationStage.BASE_DN: "디렉터리 서버에서 Base DN을 찾지 못했습니다",
    VerificationStage.BIND: "디렉터리 서버가 바인드를 처리하지 못했습니다",
    VerificationStage.SEARCH: "디렉터리 서버에서 사용자를 조회하지 못했습니다",
}
_TLS_TYPES = (ssl.SSLError, LDAPStartTLSError, LDAPSSLConfigurationError, LDAPSSLNotSupportedError)
_TLS_HINTS = ("ssl", "tls", "certificate")


def failure_stage(error: BaseException) -> VerificationStage:
    """예외가 TLS 단계 문제인지(그 밖의 소켓·타임아웃·프로토콜 오류는 CONNECT) 분류한다."""
    if isinstance(error, _TLS_TYPES):
        return VerificationStage.TLS
    # ldap3은 소켓 래핑 중의 SSL 실패를 LDAPSocketOpenError 문자열로 바꾼다.
    if any(isinstance(cause, ssl.SSLError) for cause in (error.__cause__, error.__context__)):
        return VerificationStage.TLS
    text = str(error).lower()
    if "wrapping" in text and any(hint in text for hint in _TLS_HINTS):
        return VerificationStage.TLS
    return VerificationStage.CONNECT


def unavailable(stage: VerificationStage) -> DirectoryUnavailableError:
    return DirectoryUnavailableError(MESSAGES[stage], stage=stage)


def bind_failure(code: object) -> DirectoryUnavailableError | InvalidCredentialsError:
    """bind 결과 코드를 자격증명 오류(49·50·53) 또는 서버 측 장애로 나눈다."""
    if code in CREDENTIAL_REJECTION_CODES:
        return InvalidCredentialsError(
            "아이디 또는 비밀번호가 올바르지 않습니다", stage=VerificationStage.BIND
        )
    return unavailable(VerificationStage.BIND)


def service_bind_failure(code: object) -> DirectoryUnavailableError:
    """서비스 계정 bind 실패. 거부(49·50·53)는 설정 오류, 그 밖은 서버 측 장애."""
    if code in CREDENTIAL_REJECTION_CODES:
        return DirectoryMisconfiguredError(
            MESSAGES[VerificationStage.SERVICE_BIND], stage=VerificationStage.SERVICE_BIND
        )
    return unavailable(VerificationStage.SERVICE_BIND)
