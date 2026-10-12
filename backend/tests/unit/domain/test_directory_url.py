"""T-D12·D13·D21: DirectoryUrl.parse (DS-2). scheme·host는 소문자, IPv6 host는 대괄호 없이."""

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.directory.settings import DirectoryUrl


@pytest.mark.parametrize(
    ("text", "scheme", "host", "port"),
    [
        ("ldaps://dc1.corp", "ldaps", "dc1.corp", 636),
        ("ldap://dc1", "ldap", "dc1", 389),
        ("ldaps://dc1.corp.test:3269", "ldaps", "dc1.corp.test", 3269),
        ("ldap://dc1:1", "ldap", "dc1", 1),
        ("ldaps://dc1:65535", "ldaps", "dc1", 65535),
        ("ldaps://10.0.0.5", "ldaps", "10.0.0.5", 636),
        ("ldaps://[::1]", "ldaps", "::1", 636),
        ("ldap://[2001:db8::1]:390", "ldap", "2001:db8::1", 390),
        ("LDAPS://DC1.Corp", "ldaps", "dc1.corp", 636),
    ],
)
def test_directory_url_accepts_ldaps_and_ldap_with_default_ports(
    text: str, scheme: str, host: str, port: int
) -> None:
    url = DirectoryUrl.parse(text)

    assert (url.scheme, url.host, url.port) == (scheme, host, port)


def test_urls_that_differ_only_by_default_port_are_equal() -> None:
    assert DirectoryUrl.parse("ldaps://dc1") == DirectoryUrl.parse("ldaps://dc1:636")


@pytest.mark.parametrize(
    "text",
    [
        "",
        "dc1.corp",
        "http://dc1.corp",
        "ldapi://dc1.corp",
        "ftp://dc1",
        "ldaps://",
        "ldaps://dc1/ou=users",
        "ldaps://dc1/dc=corp?sub",
        "ldaps://user@dc1",
        "ldaps://user:pw@dc1",
        "ldaps://dc1?attr=1",
        "ldaps://dc1#frag",
        "ldaps://dc1:0",
        "ldaps://dc1:65536",
        "ldaps://dc1:-1",
        "ldaps://dc1:abc",
        "ldaps://dc1:",
        "ldaps://dc 1",
        "ldaps://-bad.corp",
        "ldaps://bad-.corp",
        "ldaps://bad_name.corp",
        "ldaps://a..b",
        "ldaps://" + "a" * 64 + ".corp",
        "ldaps://" + ".".join(["a" * 60] * 5),
        "ldaps://[::1",
        "ldaps://[zzz]",
        "ldaps://dc1\x00",
    ],
)
def test_directory_url_rejects_bad_scheme_path_userinfo_query_port(text: str) -> None:
    with pytest.raises(InvalidValueError):
        DirectoryUrl.parse(text)


def test_directory_url_accepts_the_longest_valid_hostname() -> None:
    host = ".".join(["a" * 61, "b" * 61, "c" * 61, "d" * 61])  # 247 chars

    assert DirectoryUrl.parse(f"ldaps://{host}").host == host
