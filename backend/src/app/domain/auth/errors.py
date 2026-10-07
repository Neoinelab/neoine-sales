from app.domain.common.errors import DomainError


class AuthenticationError(DomainError):
    """로그인하지 않았거나 세션·토큰이 유효하지 않다."""


class AccessDeniedError(DomainError):
    """인증은 됐지만 이 시스템을 쓸 권한(그룹)이 없다."""
