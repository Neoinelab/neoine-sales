"""요청 출처 정보. 프록시 헤더(X-Forwarded-For)는 신뢰 정책이 정해지기 전까지 읽지 않는다."""

from fastapi import Request

UNKNOWN_IP = "unknown"


def client_ip(request: Request) -> str:
    """TCP 연결의 상대 주소(request.client.host). 리버스 프록시 뒤에서는 프록시 주소가 된다."""
    return request.client.host if request.client else UNKNOWN_IP
