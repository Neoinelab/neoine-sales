"""요청 출처 정보.

프록시 정책: nginx가 X-Forwarded-For를 실제 접속 주소로 덮어쓰고,
api(uvicorn)는 compose 내부 대역(172.29.40.0/24)의 프록시 헤더만 신뢰한다.
"""

from fastapi import Request

UNKNOWN_IP = "unknown"


def client_ip(request: Request) -> str:
    """접속 주소(request.client.host).

    uvicorn이 신뢰 대역 프록시의 X-Forwarded-For로 바꿔 둔 실제 접속 주소다(모듈 docstring 참고).
    """
    return request.client.host if request.client else UNKNOWN_IP
