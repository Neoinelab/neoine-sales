"""UploadCandidate.check(P2b AC-08): 목업 `validateUpload` 순서에 파일 이름 규칙을 더한 업로드 검증.

순서: 파일 없음 -> 설명 -> 크기 -> 차단 확장자 -> 파일 이름. 처음 걸린 위반만 알린다.
"""

import pytest

from app.domain.attachment.values import (
    BLOCKED_EXTENSIONS,
    DESCRIPTION_TOO_LONG,
    FILE_TOO_LARGE,
    INVALID_FILE_NAME,
    MAX_FILE_BYTES,
    NO_FILE,
    FileName,
    UploadCandidate,
    blocked_message,
)
from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with

TOO_LONG = "가" * 101
OVER = MAX_FILE_BYTES + 1


def _check(
    file_name: str | None = "a.pdf", description: str = "", size: int | None = 10
) -> UploadCandidate:
    return UploadCandidate.check(file_name=file_name, description=description, size=size)


def test_a_valid_upload_yields_the_normalized_name_and_the_trimmed_description() -> None:
    candidate = _check("보고서.pdf", "  최종본  ", 1_000)

    assert candidate.file_name == FileName.parse("보고서.pdf")
    assert candidate.description == "최종본"


@pytest.mark.parametrize(
    ("file_name", "description", "size"),
    [
        ("a.tar.gz", "", 10),
        ("README", "", 10),
        ("empty.txt", "", 0),
        ("max.bin", "", MAX_FILE_BYTES),
        ("desc.txt", "😀" * 100, 10),
        ("padded.txt", " " + "가" * 100 + " ", 10),
        ("exe.txt", "", 10),
        ("a.exe.txt", "", 10),
        ("unknown-size.bin", "", None),
        (".exe", "", 10),
    ],
)
def test_boundary_uploads_are_accepted(file_name: str, description: str, size: int | None) -> None:
    assert _check(file_name, description, size).file_name.value == file_name


def test_a_missing_file_is_reported_before_everything_else() -> None:
    with raises_with(InvalidValueError, NO_FILE):
        _check(None, TOO_LONG, OVER)


def test_a_too_long_description_is_reported_before_the_size() -> None:
    with raises_with(InvalidValueError, DESCRIPTION_TOO_LONG):
        _check("a.exe", TOO_LONG, OVER)


def test_the_size_is_reported_before_the_blocked_extension() -> None:
    with raises_with(InvalidValueError, FILE_TOO_LARGE):
        _check("a.exe", "", OVER)


def test_the_blocked_extension_is_reported_before_an_unusable_name() -> None:
    with raises_with(InvalidValueError, blocked_message("exe")):
        _check("dir/a.exe")


def test_an_unusable_name_is_reported_last() -> None:
    with raises_with(InvalidValueError, INVALID_FILE_NAME):
        _check("dir/a.txt")


def test_one_byte_over_the_limit_is_rejected() -> None:
    with raises_with(InvalidValueError, FILE_TOO_LARGE):
        _check("big.bin", "", OVER)


def test_the_description_is_trimmed_before_it_is_measured() -> None:
    with raises_with(InvalidValueError, DESCRIPTION_TOO_LONG):
        _check("a.pdf", "가" * 101)


@pytest.mark.parametrize("extension", sorted(BLOCKED_EXTENSIONS))
def test_every_blocked_extension_is_rejected_whatever_its_case(extension: str) -> None:
    with raises_with(InvalidValueError, blocked_message(extension)):
        _check(f"setup.{extension.upper()}")


@pytest.mark.parametrize("raw", ["setup.exe ", "setup.exe.", "setup.EXE . ", "setup.exe..."])
def test_trailing_spaces_and_dots_do_not_hide_a_blocked_extension(raw: str) -> None:
    # Windows가 저장할 때 끝의 공백·점을 지우므로 판정도 지운 값으로 한다
    with raises_with(InvalidValueError, blocked_message("exe")):
        _check(raw)


def test_trailing_space_after_an_allowed_extension_is_not_blocked() -> None:
    assert _check("report.pdf ").file_name.value == "report.pdf "


def test_the_blocked_message_uses_the_lowercase_extension() -> None:
    with raises_with(InvalidValueError, "실행·설치 파일(.msi)은 업로드할 수 없습니다."):
        _check("SETUP.MSI")


def test_a_nul_in_the_description_is_rejected() -> None:
    with pytest.raises(InvalidValueError, match="NUL"):
        _check("a.pdf", "a\x00b")
