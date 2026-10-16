"""다운로드 Content-Disposition 헤더 값(P2b AC-13, 7.3): ASCII 대체 이름과 RFC 5987 UTF-8 이름.

`attachment_disposition(file_name)`은 헤더 값 전체
`attachment; filename="<ASCII 대체>"; filename*=UTF-8''<퍼센트 인코딩>`을 돌려준다.
대체 이름은 비ASCII 문자(코드 포인트마다)·`"`·`\\`를 `_`로 바꾼다.
"""

from urllib.parse import unquote

import pytest
from app.web.content_disposition import attachment_disposition

NASTY_NAMES = [
    "report.pdf",
    "견적서 최종 (1).pdf",
    'quote "final".pdf',
    "back\\slash.txt",
    "semi;colon,comma=eq.txt",
    "100% sure's*.txt",
    "😀 emoji.png",
    "a\r\nSet-Cookie: x=1.txt",
]


def test_an_ascii_name_is_the_same_in_both_parameters() -> None:
    assert attachment_disposition("report.pdf") == (
        "attachment; filename=\"report.pdf\"; filename*=UTF-8''report.pdf"
    )


def test_a_korean_name_gets_an_underscore_per_character_and_a_percent_encoded_utf8_name() -> None:
    assert attachment_disposition("견적서 v2.pdf") == (
        "attachment; filename=\"___ v2.pdf\"; filename*=UTF-8''%EA%B2%AC%EC%A0%81%EC%84%9C%20v2.pdf"
    )


def test_a_name_with_a_quote_and_a_backslash_cannot_break_out_of_the_quoted_string() -> None:
    header = attachment_disposition('a"b\\c.txt')

    assert header.startswith('attachment; filename="a_b_c.txt"; ')
    assert header.endswith("filename*=UTF-8''a%22b%5Cc.txt")


def test_reserved_characters_are_percent_encoded_in_the_utf8_name() -> None:
    header = attachment_disposition("a b(1)'s*.txt")

    assert header.endswith("filename*=UTF-8''a%20b%281%29%27s%2A.txt")


@pytest.mark.parametrize("name", NASTY_NAMES)
def test_the_header_never_contains_a_line_break(name: str) -> None:
    header = attachment_disposition(name)

    assert "\r" not in header
    assert "\n" not in header


@pytest.mark.parametrize("name", [n for n in NASTY_NAMES if "\r" not in n])
def test_the_utf8_name_decodes_back_to_the_original_name(name: str) -> None:
    header = attachment_disposition(name)

    encoded = header.split("filename*=UTF-8''", 1)[1]
    assert unquote(encoded) == name


@pytest.mark.parametrize("name", NASTY_NAMES)
def test_the_fallback_name_is_plain_ascii_without_quote_or_backslash(name: str) -> None:
    header = attachment_disposition(name)

    fallback = header.split('filename="', 1)[1].split('"; filename*=', 1)[0]
    assert fallback.isascii()
    assert '"' not in fallback
    assert "\\" not in fallback
