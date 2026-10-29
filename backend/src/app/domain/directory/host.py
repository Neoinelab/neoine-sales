"""AD 호스트 입력 규칙. 호스트 이름·IPv4·IPv6 리터럴만 받고 소문자로 맞춘다.

scheme·포트·경로는 별도 입력이거나 허용하지 않는다. IPv6는 대괄호 없이 입력·저장한다.
"""

import ipaddress
import re

from app.domain.common.errors import InvalidValueError

HOST_MAX = 253
_LABEL = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?")


def _fail(reason: str) -> InvalidValueError:
    return InvalidValueError(f"host: {reason}")


def normalize_host(raw: str) -> str:
    host = raw.lower()
    if ":" in host:
        return _normalize_ipv6(host)
    if not host or len(host) > HOST_MAX:
        raise _fail(f"호스트는 1~{HOST_MAX}자여야 합니다")
    labels = host.split(".")
    if any(_LABEL.fullmatch(label) is None for label in labels):
        raise _fail("호스트 이름 형식이 올바르지 않습니다(주소·포트·경로 없이 이름만 입력)")
    if all(label.isdigit() for label in labels):
        try:
            return str(ipaddress.IPv4Address(host))
        except ValueError:
            raise _fail("IPv4 주소 형식이 올바르지 않습니다") from None
    return host


def _normalize_ipv6(host: str) -> str:
    try:
        return str(ipaddress.IPv6Address(host))
    except ValueError:
        raise _fail("IPv6 주소 형식이 올바르지 않습니다(대괄호 없이 입력)") from None
