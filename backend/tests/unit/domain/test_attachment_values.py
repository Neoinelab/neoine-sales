"""첨부 값과 한도(P2b AC-08): 상수·문구, 확장자 판정, 설명 검증, 스트리밍 한도."""

import pytest

from app.domain.attachment.values import (
    BLOCKED_EXTENSIONS,
    DESCRIPTION_MAX,
    DESCRIPTION_TOO_LONG,
    FILE_NAME_MAX,
    FILE_TOO_LARGE,
    INVALID_FILE_NAME,
    MAX_FILE_BYTES,
    NO_FILE,
    OnExists,
    blocked_message,
    ensure_within_limit,
    extension_of,
    parse_description,
)
from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with

PRD_BLOCKED = ["exe", "msi", "bat", "cmd", "sh", "ps1", "jar", "com", "scr", "dmg", "pkg"]
PRD_BLOCKED += ["deb", "rpm"]
EXTRA_BLOCKED = ["vbs", "vbe", "wsf", "wsh", "hta", "cpl", "msp", "mst", "apk", "appimage", "run"]


def test_the_limits_and_messages_are_the_fixed_values() -> None:
    assert MAX_FILE_BYTES == 104_857_600
    assert (DESCRIPTION_MAX, FILE_NAME_MAX) == (100, 255)
    assert NO_FILE == "업로드할 파일을 선택하세요."
    assert DESCRIPTION_TOO_LONG == "설명은 100자 이내로 입력하세요."
    assert FILE_TOO_LARGE == "파일 크기가 100MB를 초과합니다. (최대 100MB)"
    assert INVALID_FILE_NAME == "사용할 수 없는 파일 이름입니다."


def test_blocked_extensions_are_the_prd_list_plus_the_eleven_decided_ones() -> None:
    assert frozenset(PRD_BLOCKED + EXTRA_BLOCKED) == BLOCKED_EXTENSIONS
    assert len(BLOCKED_EXTENSIONS) == 24


@pytest.mark.parametrize("extension", ["zip", "gz", "pdf", "txt", "docx", "exe2", ""])
def test_ordinary_and_archive_extensions_are_not_blocked(extension: str) -> None:
    assert extension not in BLOCKED_EXTENSIONS


def test_blocked_message_names_the_extension() -> None:
    assert blocked_message("exe") == "실행·설치 파일(.exe)은 업로드할 수 없습니다."


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("a.tar.gz", "gz"),
        ("run.EXE", "exe"),
        ("Setup.MsI", "msi"),
        ("a.exe.txt", "txt"),
        (".bashrc", ""),
        ("a.", ""),
        ("README", ""),
        ("", ""),
        ("한글.PDF", "pdf"),
        (".exe", ""),
        ("setup.exe ", "exe"),
        ("setup.exe.", "exe"),
        ("setup.EXE . ", "exe"),
        ("report.pdf ", "pdf"),
        ("a. .", ""),
        (".exe.", ""),
    ],
)
def test_extension_of_is_the_lowercase_last_extension(name: str, expected: str) -> None:
    assert extension_of(name) == expected


def test_on_exists_has_the_three_wire_values() -> None:
    assert [m.value for m in OnExists] == ["ask", "replace", "skip"]
    assert OnExists("ask") is OnExists.ASK


def test_on_exists_rejects_an_unknown_value() -> None:
    with pytest.raises(ValueError, match="overwrite"):
        OnExists("overwrite")


def test_parse_description_trims_and_keeps_inner_whitespace() -> None:
    assert parse_description("  견적서  최종 \n") == "견적서  최종"


def test_parse_description_of_blank_text_is_empty() -> None:
    assert parse_description(" \t ") == ""


def test_parse_description_accepts_exactly_100_code_points() -> None:
    assert parse_description("😀" * 100) == "😀" * 100


def test_parse_description_counts_code_points_after_trimming() -> None:
    padded = "  " + "가" * 100 + "  "

    assert parse_description(padded) == "가" * 100


def test_parse_description_rejects_101_code_points() -> None:
    with raises_with(InvalidValueError, DESCRIPTION_TOO_LONG):
        parse_description("😀" * 101)


def test_parse_description_rejects_nul_even_when_otherwise_valid() -> None:
    with pytest.raises(InvalidValueError, match="NUL"):
        parse_description("견적\x00서")


def test_ensure_within_limit_allows_zero_and_the_exact_maximum() -> None:
    ensure_within_limit(0)
    ensure_within_limit(MAX_FILE_BYTES)


def test_ensure_within_limit_rejects_one_byte_over() -> None:
    with raises_with(InvalidValueError, FILE_TOO_LARGE):
        ensure_within_limit(MAX_FILE_BYTES + 1)
