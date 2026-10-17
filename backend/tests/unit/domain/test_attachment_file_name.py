"""FileName 값 객체(P2b AC-08·10, 계획 12.2-3): NFC 정규화와 사용할 수 없는 이름 거절."""

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
    assert FileName.parse(raw).value == unicodedata.normalize("NFC", raw)


def test_parse_keeps_leading_and_trailing_spaces() -> None:
    assert FileName.parse("  a.pdf  ").value == "  a.pdf  "


def test_parse_normalizes_a_decomposed_name_to_nfc() -> None:
    decomposed = unicodedata.normalize("NFD", KOREAN_NFC)
    assert decomposed != KOREAN_NFC

    assert FileName.parse(decomposed).value == KOREAN_NFC


def test_composed_and_decomposed_spellings_are_the_same_name() -> None:
    decomposed = unicodedata.normalize("NFD", KOREAN_NFC)

    assert FileName.parse(decomposed) == FileName.parse(KOREAN_NFC)


def test_names_that_differ_only_by_case_are_different_names() -> None:
    assert FileName.parse("Report.PDF") != FileName.parse("report.pdf")


def test_the_length_limit_counts_the_normalized_form() -> None:
    decomposed = unicodedata.normalize("NFD", "한" * FILE_NAME_MAX)
    assert len(decomposed) > FILE_NAME_MAX

    assert FileName.parse(decomposed).value == "한" * FILE_NAME_MAX


def test_parse_rejects_one_code_point_over_the_limit_after_normalizing() -> None:
    with raises_with(InvalidValueError, INVALID_FILE_NAME):
        FileName.parse("한" * (FILE_NAME_MAX + 1))


@pytest.mark.parametrize(
    ("raw", "extension"),
    [("a.tar.gz", "gz"), ("Run.EXE", "exe"), (".bashrc", ""), ("README", ""), ("a.", "")],
)
def test_extension_is_the_lowercase_last_one(raw: str, extension: str) -> None:
    assert FileName.parse(raw).extension == extension


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
    with raises_with(InvalidValueError, INVALID_FILE_NAME):
        FileName.parse(template.format(chr(code_point)))


def test_parse_accepts_right_to_left_letters_without_format_characters() -> None:
    assert FileName.parse("שלום.pdf").value == "שלום.pdf"


# 2026-10-17 사용자 결정(R3 리뷰 가능성 1): 유니코드 서식 문자(Cf) 전체를 이름 어디에서든 거부한다.
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
    assert unicodedata.category(mark) == "Cf"

    with raises_with(InvalidValueError, INVALID_FILE_NAME):
        FileName.parse(template.format(m=mark))


@pytest.mark.parametrize("raw", ["setup.exe\ufeff", "setup.exe\u200b"])
def test_parse_rejects_an_executable_name_disguised_by_a_trailing_format_character(
    raw: str,
) -> None:
    with raises_with(InvalidValueError, INVALID_FILE_NAME):
        FileName.parse(raw)


def test_parse_rejects_a_zwj_emoji_sequence_because_zwj_is_a_format_character() -> None:
    # user-visible impact: such emoji names are refused
    family = "\U0001f468\u200d\U0001f469\u200d\U0001f467"

    with raises_with(InvalidValueError, INVALID_FILE_NAME):
        FileName.parse(f"{family}.png")


@pytest.mark.parametrize("raw", ["\U0001f600.png", "❤️.png", "한글\U0001f44d.pdf"])
def test_parse_still_accepts_korean_and_emoji_without_format_characters(raw: str) -> None:
    assert FileName.parse(raw).value == unicodedata.normalize("NFC", raw)
