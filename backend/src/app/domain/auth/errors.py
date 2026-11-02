from app.domain.common.errors import DomainError, InvalidValueError


class AuthenticationError(DomainError):
    """로그인하지 않았거나 세션·토큰이 유효하지 않다."""


class AccessDeniedError(DomainError):
    """인증은 됐지만 이 시스템을 쓸 권한(그룹)이 없다."""


class TooManyAttemptsError(DomainError):
    """로그인 실패가 제한을 넘어 잠시 시도할 수 없다(429)."""


class WeakPasswordError(InvalidValueError):
    """새 비밀번호가 정책(길이·아이디 동일)을 지키지 않는다(422)."""


class WrongCurrentPasswordError(InvalidValueError):
    """비밀번호 변경에서 현재 비밀번호가 맞지 않는다(422, 401이 아니다)."""
