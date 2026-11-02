"""compose가 api에 주는 `--forwarded-allow-ips`로 위조 X-Forwarded-For를 막는지(리뷰 Blocker).

compose.yaml의 api command에서 신뢰 대역을 읽어 uvicorn ProxyHeadersMiddleware에 그대로 준다.
프록시(신뢰 대역 안의 주소)가 연결하고, 클라이언트가 보낸 위조 값 뒤에 실제 주소가 붙은
헤더가 오면 `client_ip`는 실제 주소여야 한다. 값이 `*`이면 맨 앞 위조 값이 채택되어 실패한다.
"""

import ipaddress
import re
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.web.request_info import client_ip

COMPOSE = Path(__file__).resolve().parents[4] / "infra" / "docker" / "compose.yaml"
REAL_CLIENT = "203.0.113.9"
FORGED = "1.2.3.4"


def _allow_ips() -> str:
    text = COMPOSE.read_text(encoding="utf-8")
    match = re.search(r"--forwarded-allow-ips(?:=|[\s'\",-]+)([^\s'\",]+)", text)
    assert match, "compose.yaml의 api command에 --forwarded-allow-ips가 없음"
    return match.group(1)


def _proxy_address(allow: str) -> str:
    first = allow.split(",", maxsplit=1)[0]
    if first == "*":
        return "172.18.0.5"
    if "/" in first:
        return str(ipaddress.ip_network(first, strict=False).network_address + 2)
    return first


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/ip")
    async def ip(request: Request) -> dict[str, str]:
        return {"ip": client_ip(request)}

    return app


async def _seen_ip(xff: str) -> str:
    allow = _allow_ips()
    wrapped: Any = ProxyHeadersMiddleware(cast("Any", _app()), trusted_hosts=allow)
    transport = ASGITransport(app=wrapped, client=(_proxy_address(allow), 40000))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ip", headers={"X-Forwarded-For": xff})
    return str(response.json()["ip"])


def test_trusted_range_is_not_a_wildcard() -> None:
    assert _allow_ips() != "*"


async def test_forged_leading_address_is_not_used_as_the_client_ip() -> None:
    assert await _seen_ip(f"{FORGED}, {REAL_CLIENT}") == REAL_CLIENT


async def test_single_address_from_the_proxy_is_used() -> None:
    assert await _seen_ip(REAL_CLIENT) == REAL_CLIENT
