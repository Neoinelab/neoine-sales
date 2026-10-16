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
