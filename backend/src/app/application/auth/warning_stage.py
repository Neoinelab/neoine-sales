from enum import StrEnum


class DirectoryWarningStage(StrEnum):
    """AD가 답하지 못해 대체 로그인으로 넘어간 이유(admin 경고 팝업과 로그에 쓴다)."""

    NOT_CONFIGURED = "not_configured"
    CONNECT = "connect"
    TLS = "tls"
    SERVICE_BIND = "service_bind"
    BASE_DN = "base_dn"
    SEARCH = "search"
    CREDENTIAL_UNREADABLE = "credential_unreadable"
    UNKNOWN = "unknown"
