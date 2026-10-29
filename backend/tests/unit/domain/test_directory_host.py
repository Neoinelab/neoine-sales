"""normalize_host: AD 호스트 입력 규칙(2026-10-29 개편). 호스트 이름·IPv4·IPv6만, 소문자로 맞춘다.

예전 `DirectoryUrl`(scheme·port·경로를 가진 URL)은 없어졌다. 포트·보안 연결은 별도 입력이다.
"""

import importlib.util

import pytest
from app.domain.directory.host import normalize_host

from app.domain.common.errors import InvalidValueError


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("dc1.corp", "dc1.corp"),
        ("dc1", "dc1"),
        ("DC1.Corp.Test", "dc1.corp.test"),
        ("10.0.0.5", "10.0.0.5"),
        ("::1", "::1"),
        ("2001:db8::1", "2001:db8::1"),
        ("2001:DB8::1", "2001:db8::1"),
    ],
)
def test_host_names_and_ip_literals_are_accepted_and_lowercased(text: str, expected: str) -> None:
    assert normalize_host(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "ldaps://dc1.corp",
        "ldap://dc1",
        "dc1.corp:636",
        "dc1/ou=users",
        "user@dc1",
        "dc1?attr=1",
        "dc1#frag",
        "dc 1",
        "-bad.corp",
        "bad-.corp",
        "bad_name.corp",
        "a..b",
        "a" * 64 + ".corp",
        ".".join(["a" * 60] * 5),
        "dc1\x00",
        "zzz::zzz",
    ],
)
def test_urls_ports_paths_and_malformed_hosts_are_rejected_with_the_field_name(text: str) -> None:
    with pytest.raises(InvalidValueError) as caught:
        normalize_host(text)

    assert "host" in str(caught.value)


def test_the_longest_valid_hostname_is_accepted() -> None:
    host = ".".join(["a" * 61, "b" * 61, "c" * 61, "d" * 61])  # 247자

    assert normalize_host(host) == host


def test_the_old_url_value_object_module_is_gone() -> None:
    assert importlib.util.find_spec("app.domain.directory.url") is None
