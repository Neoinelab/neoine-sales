"""다운로드 Content-Disposition 헤더 값(7.3): ASCII 대체 이름과 RFC 5987 UTF-8 이름.

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
    """ASCII 이름은 두 파라미터에서 같다.

    테스트 코드: AT-031
    """
    # when: ASCII 이름의 다운로드 헤더를 만든다
    header = attachment_disposition("report.pdf")

    # then: 두 파라미터가 같은 이름이다
    assert header == "attachment; filename=\"report.pdf\"; filename*=UTF-8''report.pdf"


def test_a_korean_name_gets_an_underscore_per_character_and_a_percent_encoded_utf8_name() -> None:
    """한글 이름은 글자마다 `_`인 대체 이름과 퍼센트 인코딩 UTF-8 이름을 함께 싣는다.

    테스트 코드: AT-031
    """
    # when: 한글 이름의 다운로드 헤더를 만든다
    header = attachment_disposition("견적서 v2.pdf")

    # then: 대체 이름은 글자마다 `_`이고 UTF-8 이름은 퍼센트 인코딩이다
    fallback = 'filename="___ v2.pdf"'
    encoded = "filename*=UTF-8''%EA%B2%AC%EC%A0%81%EC%84%9C%20v2.pdf"
    assert header == f"attachment; {fallback}; {encoded}"


def test_a_name_with_a_quote_and_a_backslash_cannot_break_out_of_the_quoted_string() -> None:
    """따옴표·역슬래시가 든 이름도 따옴표 문자열을 깨지 못한다.

    테스트 코드: AT-031
    """
    # when: 따옴표·역슬래시가 든 이름의 헤더를 만든다
    header = attachment_disposition('a"b\\c.txt')

    # then: 대체 이름은 `_`로 바뀌고 UTF-8 이름은 퍼센트 인코딩된다
    assert header.startswith('attachment; filename="a_b_c.txt"; ')
    assert header.endswith("filename*=UTF-8''a%22b%5Cc.txt")


def test_reserved_characters_are_percent_encoded_in_the_utf8_name() -> None:
    """예약 문자는 UTF-8 이름에서 모두 퍼센트 인코딩된다.

    테스트 코드: AT-031
    """
    # when: 공백·괄호·작은따옴표·`*`가 든 이름의 헤더를 만든다
    header = attachment_disposition("a b(1)'s*.txt")

    # then: 예약 문자가 모두 인코딩된다
    assert header.endswith("filename*=UTF-8''a%20b%281%29%27s%2A.txt")


@pytest.mark.parametrize("name", NASTY_NAMES)
def test_the_header_never_contains_a_line_break(name: str) -> None:
    """헤더에는 줄바꿈이 들어가지 않는다.

    테스트 코드: AT-031
    """
    # when: 위험한 이름의 헤더를 만든다
    header = attachment_disposition(name)

    # then: CR·LF가 없다
    assert "\r" not in header
    assert "\n" not in header


@pytest.mark.parametrize("name", [n for n in NASTY_NAMES if "\r" not in n])
def test_the_utf8_name_decodes_back_to_the_original_name(name: str) -> None:
    """UTF-8 이름을 풀면 원래 이름이 된다.

    테스트 코드: AT-031
    """
    # when: 위험한 이름의 헤더를 만든다
    header = attachment_disposition(name)

    # then: `filename*`를 풀면 원래 이름과 같다
    encoded = header.split("filename*=UTF-8''", 1)[1]
    assert unquote(encoded) == name


@pytest.mark.parametrize("name", NASTY_NAMES)
def test_the_fallback_name_is_plain_ascii_without_quote_or_backslash(name: str) -> None:
    """대체 이름은 따옴표·역슬래시 없는 ASCII다.

    테스트 코드: AT-031
    """
    # when: 위험한 이름의 헤더를 만든다
    header = attachment_disposition(name)

    # then: 대체 이름은 ASCII이고 `"`·`\`가 없다
    fallback = header.split('filename="', 1)[1].split('"; filename*=', 1)[0]
    assert fallback.isascii()
    assert '"' not in fallback
    assert "\\" not in fallback


def test_the_fallback_name_has_no_percent_sign_and_the_utf8_name_encodes_it() -> None:
    """대체 이름에는 `%`가 없고 UTF-8 이름이 `%`를 인코딩한다.

    테스트 코드: AT-031
    """
    # when: `%`가 든 이름의 헤더를 만든다
    header = attachment_disposition("100%25 sure.txt")

    # then: 대체 이름은 `_`로 바뀌고 UTF-8 이름은 `%25`로 인코딩된다
    fallback = header.split('filename="', 1)[1].split('"; filename*=', 1)[0]
    assert fallback == "100_25 sure.txt"
    assert header.endswith("filename*=UTF-8''100%2525%20sure.txt")


@pytest.mark.parametrize("name", NASTY_NAMES)
def test_the_fallback_name_never_contains_a_percent_sign(name: str) -> None:
    """어떤 이름도 대체 이름에 `%`가 남지 않는다.

    테스트 코드: AT-031
    """
    # when: 위험한 이름의 헤더를 만든다
    header = attachment_disposition(name)

    # then: 대체 이름에 `%`가 없다
    fallback = header.split('filename="', 1)[1].split('"; filename*=', 1)[0]
    assert "%" not in fallback
