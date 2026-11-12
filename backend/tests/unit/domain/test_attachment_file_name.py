"""FileName 값 객체: NFC 정규화와 사용할 수 없는 이름 거절."""

import unicodedata

import pytest

from app.domain.attachment.values import FILE_NAME_MAX, INVALID_FILE_NAME, FileName
from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with

KOREAN_NFC = "한글 견적서.pdf"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "a/b.txt",
        "/abs.txt",
        "..\\x.txt",
        "a\\b.txt",
        "\x01a.txt",
        "a\x00.txt",
        "tab\tname.txt",
        "line\nbreak.txt",
        "a\x7f.txt",
        ".",
        "..",
        "x" * (FILE_NAME_MAX + 1),
    ],
)
def test_parse_rejects_names_that_cannot_be_used(raw: str) -> None:
    """빈 이름·경로 구분자·제어 문자·`.`·`..`·255자 초과 이름은 거절된다.

    테스트 코드: AT-010
    """
    # when·then: 쓸 수 없는 이름을 해석하면 "사용할 수 없는 파일 이름입니다." 오류다
    with raises_with(InvalidValueError, INVALID_FILE_NAME):
        FileName.parse(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "a.pdf",
        "a.tar.gz",
        ".bashrc",
        "README",
        "...",
        "a..b",
        "공백 있는 이름.txt",
        " leading and trailing ",
        KOREAN_NFC,
        "x" * FILE_NAME_MAX,
        "😀" * FILE_NAME_MAX,
        "a:b*c?d.txt",
    ],
)
def test_parse_accepts_ordinary_names_unchanged(raw: str) -> None:
    """평범한 이름(점으로 시작·공백 포함·255자·이모지 등)은 NFC 값 그대로 받아들인다.

    테스트 코드: AT-010
    """
    # when: 이름을 해석한다
    name = FileName.parse(raw).value

    # then: 해석한 값이 NFC로 정규화한 원래 값이다
    assert name == unicodedata.normalize("NFC", raw)


def test_parse_keeps_leading_and_trailing_spaces() -> None:
    """앞뒤 공백은 자르지 않는다.

    테스트 코드: AT-010
    """
    # when: 앞뒤 공백이 있는 이름을 해석한다
    name = FileName.parse("  a.pdf  ").value

    # then: 공백이 그대로 남는다
    assert name == "  a.pdf  "


def test_parse_normalizes_a_decomposed_name_to_nfc() -> None:
    """NFD로 분해된 이름은 NFC로 정규화한다.

    테스트 코드: AT-010
    """
    # given: NFD로 분해한 한글 이름
    decomposed = unicodedata.normalize("NFD", KOREAN_NFC)
    assert decomposed != KOREAN_NFC

    # when: 이름을 해석한다
    name = FileName.parse(decomposed)

    # then: 값이 NFC 이름이다
    assert name.value == KOREAN_NFC


def test_composed_and_decomposed_spellings_are_the_same_name() -> None:
    """NFC와 NFD 표기는 같은 이름이다.

    테스트 코드: AT-021
    """
    # given: NFD로 분해한 한글 이름
    decomposed = unicodedata.normalize("NFD", KOREAN_NFC)

    # when: NFD 표기를 해석한다
    from_decomposed = FileName.parse(decomposed)

    # then: NFC 표기를 해석한 이름과 같다
    assert from_decomposed == FileName.parse(KOREAN_NFC)


def test_names_that_differ_only_by_case_are_different_names() -> None:
    """대소문자만 다른 이름은 다른 이름이다.

    테스트 코드: AT-021
    """
    # when: 대문자가 든 이름을 해석한다
    upper = FileName.parse("Report.PDF")

    # then: 소문자 이름과 같지 않다
    assert upper != FileName.parse("report.pdf")


def test_the_length_limit_counts_the_normalized_form() -> None:
    """255자 한도는 NFC 정규화 뒤의 길이로 센다.

    테스트 코드: AT-010
    """
    # given: 분해하면 255자를 넘지만 정규화하면 255자인 이름
    decomposed = unicodedata.normalize("NFD", "한" * FILE_NAME_MAX)
    assert len(decomposed) > FILE_NAME_MAX

    # when: 이름을 해석한다
    name = FileName.parse(decomposed)

    # then: 거절되지 않고 NFC 이름이 된다
    assert name.value == "한" * FILE_NAME_MAX


def test_parse_rejects_one_code_point_over_the_limit_after_normalizing() -> None:
    """정규화 뒤 256자인 이름은 거절된다.

    테스트 코드: AT-010
    """
    # when·then: 한글 256자를 해석하면 이름 오류다
    with raises_with(InvalidValueError, INVALID_FILE_NAME):
        FileName.parse("한" * (FILE_NAME_MAX + 1))


@pytest.mark.parametrize(
    ("raw", "extension"),
    [("a.tar.gz", "gz"), ("Run.EXE", "exe"), (".bashrc", ""), ("README", ""), ("a.", "")],
)
def test_extension_is_the_lowercase_last_one(raw: str, extension: str) -> None:
    """확장자는 마지막 `.` 뒤의 소문자다(맨 앞 점·끝 점·확장자 없음은 빈 값).

    테스트 코드: AT-009
    """
    # when: 이름의 확장자를 읽는다
    actual = FileName.parse(raw).extension

    # then: 확장자가 기대 값이다
    assert actual == extension


BIDI_CONTROLS = [
    *range(0x202A, 0x202F),  # LRE RLE PDF LRO RLO
    *range(0x2066, 0x206A),  # LRI RLI FSI PDI
    0x200E,  # LRM
    0x200F,  # RLM
    0x061C,  # ALM
]


@pytest.mark.parametrize("code_point", BIDI_CONTROLS, ids=lambda cp: f"U+{cp:04X}")
@pytest.mark.parametrize("template", ["a{}b.pdf", "{}a.pdf", "a.pdf{}"])
def test_parse_rejects_a_name_with_a_bidirectional_format_character(
    code_point: int, template: str
) -> None:
    """방향 제어 문자가 든 이름은 어디에 있든 거절된다.

    테스트 코드: AT-010
    """
    # when·then: 방향 제어 문자를 이름 앞·중간·뒤에 넣어 해석하면 이름 오류다
    with raises_with(InvalidValueError, INVALID_FILE_NAME):
        FileName.parse(template.format(chr(code_point)))


def test_parse_accepts_right_to_left_letters_without_format_characters() -> None:
    """서식 문자 없는 오른쪽→왼쪽 글자 이름은 받아들인다.

    테스트 코드: AT-010
    """
    # when: 히브리어 이름을 해석한다
    name = FileName.parse("שלום.pdf").value

    # then: 이름이 그대로 받아들여진다
    assert name == "שלום.pdf"


# 2026-10-17 사용자 결정: 유니코드 서식 문자(Cf) 전체를 이름 어디에서든 거부한다.
CF_CHARS = {
    "BOM": "\ufeff",
    "ZWSP": "\u200b",
    "ZWNJ": "\u200c",
    "ZWJ": "\u200d",
    "WORD_JOINER": "\u2060",
    "SOFT_HYPHEN": "\u00ad",
    "LRM": "\u200e",
    "RLO": "\u202e",
}


@pytest.mark.parametrize("mark", list(CF_CHARS.values()), ids=list(CF_CHARS))
@pytest.mark.parametrize("template", ["{m}report.pdf", "re{m}port.pdf", "report.pdf{m}"])
def test_parse_rejects_a_format_character_anywhere_in_the_name(mark: str, template: str) -> None:
    """유니코드 서식 문자(Cf)는 이름 어디에서든 거절된다.

    테스트 코드: AT-010
    """
    # given: 서식 문자(Cf)
    assert unicodedata.category(mark) == "Cf"

    # when·then: 서식 문자를 앞·중간·뒤에 넣어 해석하면 이름 오류다
    with raises_with(InvalidValueError, INVALID_FILE_NAME):
        FileName.parse(template.format(m=mark))


@pytest.mark.parametrize("raw", ["setup.exe\ufeff", "setup.exe\u200b"])
def test_parse_rejects_an_executable_name_disguised_by_a_trailing_format_character(
    raw: str,
) -> None:
    """끝의 서식 문자로 실행 파일 이름을 위장할 수 없다.

    테스트 코드: AT-009
    """
    # when·then: "setup.exe"+서식 문자를 해석하면 이름 오류다
    with raises_with(InvalidValueError, INVALID_FILE_NAME):
        FileName.parse(raw)


def test_parse_rejects_a_zwj_emoji_sequence_because_zwj_is_a_format_character() -> None:
    # user-visible impact: such emoji names are refused
    """ZWJ 이모지 시퀀스는 ZWJ가 서식 문자라 거절된다.

    테스트 코드: AT-010
    """
    # given: ZWJ로 이어진 가족 이모지
    family = "\U0001f468\u200d\U0001f469\u200d\U0001f467"

    # when·then: 그 이름을 해석하면 이름 오류다
    with raises_with(InvalidValueError, INVALID_FILE_NAME):
        FileName.parse(f"{family}.png")


@pytest.mark.parametrize("raw", ["\U0001f600.png", "❤️.png", "한글\U0001f44d.pdf"])
def test_parse_still_accepts_korean_and_emoji_without_format_characters(raw: str) -> None:
    """서식 문자 없는 한글·이모지 이름은 받아들인다.

    테스트 코드: AT-010
    """
    # when: 한글·이모지 이름을 해석한다
    name = FileName.parse(raw).value

    # then: NFC 값 그대로 받아들여진다
    assert name == unicodedata.normalize("NFC", raw)
