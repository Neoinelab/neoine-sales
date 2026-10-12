import ipaddress
import re
from dataclasses import dataclass

from app.domain.common.errors import InvalidValueError

DEFAULT_PORTS = {"ldap": 389, "ldaps": 636}
HOST_MAX = 253
PORT_MAX = 65535
_LABEL = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?")
_FORBIDDEN = re.compile(r"[/?#@\s\x00-\x1f\x7f]")


def _fail(reason: str) -> InvalidValueError:
    return InvalidValueError(f"server_urls: {reason}")


@dataclass(frozen=True, slots=True)
class DirectoryUrl:
    """AD 서버 주소. scheme·host는 소문자, 포트는 생략하면 기본값, IPv6 host는 대괄호 없이 둔다."""

    scheme: str
    host: str
    port: int

    @classmethod
    def parse(cls, text: str) -> DirectoryUrl:
        scheme, separator, rest = text.partition("://")
        scheme = scheme.lower()
        if not separator or scheme not in DEFAULT_PORTS:
            raise _fail("ldaps:// 또는 ldap:// 로 시작해야 합니다")
        if _FORBIDDEN.search(rest):
            raise _fail("경로·쿼리·사용자 정보·공백·제어문자는 쓸 수 없습니다")
        host, port_text = _split_host_port(rest)
        port = DEFAULT_PORTS[scheme] if port_text is None else _parse_port(port_text)
        return cls(scheme=scheme, host=_normalize_host(host), port=port)

    @property
    def uri(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{self.scheme}://{host}:{self.port}"


def _split_host_port(rest: str) -> tuple[str, str | None]:
    if rest.startswith("["):
        host, bracket, tail = rest[1:].partition("]")
        if not bracket or ":" not in host or (tail and not tail.startswith(":")):
            raise _fail("IPv6 주소 형식이 올바르지 않습니다")
        return host, tail[1:] if tail else None
    if rest.count(":") > 1:
        raise _fail("포트 형식이 올바르지 않습니다")
    host, separator, port_text = rest.partition(":")
    return host, port_text if separator else None


def _parse_port(text: str) -> int:
    if not (text.isascii() and text.isdigit()) or not 1 <= int(text) <= PORT_MAX:
        raise _fail("포트는 1~65535 사이의 숫자여야 합니다")
    return int(text)


def _normalize_host(raw: str) -> str:
    host = raw.lower()
    if ":" in host:
        try:
            return str(ipaddress.IPv6Address(host))
        except ValueError:
            raise _fail("IPv6 주소 형식이 올바르지 않습니다") from None
    if not host or len(host) > HOST_MAX:
        raise _fail(f"호스트는 1~{HOST_MAX}자여야 합니다")
    labels = host.split(".")
    if any(_LABEL.fullmatch(label) is None for label in labels):
        raise _fail("호스트 이름 형식이 올바르지 않습니다")
    if all(label.isdigit() for label in labels):
        try:
            return str(ipaddress.IPv4Address(host))
        except ValueError:
            raise _fail("IPv4 주소 형식이 올바르지 않습니다") from None
    return host
