"""UploadCandidate.check: 목업 `validateUpload` 순서에 파일 이름 규칙을 더한 업로드 검증.

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
    """올바른 업로드는 정규화한 이름과 공백 제거한 설명을 돌려준다.

    테스트 코드: AT-001
    """
    # when: 이름과 앞뒤 공백 설명을 검증한다
    candidate = _check("보고서.pdf", "  최종본  ", 1_000)

    # then: 이름은 NFC 파일명이고 설명은 공백이 제거된다
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
    """경계값 업로드(확장자 없음·이중 확장자·0바이트·정확히 100MB·설명 100자)는 통과한다.

    테스트 코드: AT-005
    """
    # when: 경계값 업로드를 검증한다
    candidate = _check(file_name, description, size).file_name.value

    # then: 검증을 통과하고 이름이 그대로다
    assert candidate == file_name


def test_a_missing_file_is_reported_before_everything_else() -> None:
    """파일 없음이 다른 위반보다 먼저 보고된다.

    테스트 코드: AT-008
    """
    # when·then: 설명·크기도 어겼지만 파일 없음 문구다
    with raises_with(InvalidValueError, NO_FILE):
        _check(None, TOO_LONG, OVER)


def test_a_too_long_description_is_reported_before_the_size() -> None:
    """설명 위반이 크기·확장자 위반보다 먼저다.

    테스트 코드: AT-008
    """
    # when·then: 설명 101자, 크기 초과, 차단 확장자이면 설명 문구다
    with raises_with(InvalidValueError, DESCRIPTION_TOO_LONG):
        _check("a.exe", TOO_LONG, OVER)


def test_the_size_is_reported_before_the_blocked_extension() -> None:
    """크기 위반이 차단 확장자보다 먼저다.

    테스트 코드: AT-008
    """
    # when·then: 크기 초과와 차단 확장자이면 크기 문구다
    with raises_with(InvalidValueError, FILE_TOO_LARGE):
        _check("a.exe", "", OVER)


def test_the_blocked_extension_is_reported_before_an_unusable_name() -> None:
    """차단 확장자가 쓸 수 없는 이름보다 먼저다.

    테스트 코드: AT-008
    """
    # when·then: "dir/a.exe"이면 차단 확장자 문구다
    with raises_with(InvalidValueError, blocked_message("exe")):
        _check("dir/a.exe")


def test_an_unusable_name_is_reported_last() -> None:
    """쓸 수 없는 이름은 마지막에 보고된다.

    테스트 코드: AT-008
    """
    # when·then: "dir/a.txt"이면 이름 문구다
    with raises_with(InvalidValueError, INVALID_FILE_NAME):
        _check("dir/a.txt")


def test_one_byte_over_the_limit_is_rejected() -> None:
    """한도보다 1바이트 큰 파일은 거절된다.

    테스트 코드: AT-006
    """
    # when·then: 100MB+1바이트이면 크기 문구다
    with raises_with(InvalidValueError, FILE_TOO_LARGE):
        _check("big.bin", "", OVER)


def test_the_description_is_trimmed_before_it_is_measured() -> None:
    """설명은 공백을 자른 뒤 길이를 잰다(101자는 거절).

    테스트 코드: AT-006
    """
    # when·then: 한글 101자이면 설명 문구다
    with raises_with(InvalidValueError, DESCRIPTION_TOO_LONG):
        _check("a.pdf", "가" * 101)


@pytest.mark.parametrize("extension", sorted(BLOCKED_EXTENSIONS))
def test_every_blocked_extension_is_rejected_whatever_its_case(extension: str) -> None:
    """차단 확장자는 대소문자와 상관없이 모두 거절된다.

    테스트 코드: AT-009
    """
    # when·then: 대문자 확장자를 올리면 소문자 확장자 문구로 거절된다
    with raises_with(InvalidValueError, blocked_message(extension)):
        _check(f"setup.{extension.upper()}")


@pytest.mark.parametrize("raw", ["setup.exe ", "setup.exe.", "setup.EXE . ", "setup.exe..."])
def test_trailing_spaces_and_dots_do_not_hide_a_blocked_extension(raw: str) -> None:
    # Windows가 저장할 때 끝의 공백·점을 지우므로 판정도 지운 값으로 한다
    """끝의 공백·점으로 차단 확장자를 숨길 수 없다.

    테스트 코드: AT-009
    """
    # when·then: 끝에 공백·점이 붙은 ".exe"는 거절된다
    with raises_with(InvalidValueError, blocked_message("exe")):
        _check(raw)


@pytest.mark.parametrize("raw", ["setup.exe\u3000", "setup.exe\u00a0", "setup.exe\u2003 ."])
def test_trailing_unicode_whitespace_does_not_hide_a_blocked_extension(raw: str) -> None:
    """끝의 유니코드 공백으로 차단 확장자를 숨길 수 없다.

    테스트 코드: AT-009
    """
    # when·then: 끝에 유니코드 공백이 붙은 ".exe"는 거절된다
    with raises_with(InvalidValueError, blocked_message("exe")):
        _check(raw)


def test_trailing_space_after_an_allowed_extension_is_not_blocked() -> None:
    """허용 확장자 뒤 공백은 차단되지 않고 이름은 그대로다.

    테스트 코드: AT-009
    """
    # when: 허용 확장자 뒤에 공백이 있는 이름을 검증한다
    candidate = _check("report.pdf ").file_name.value

    # then: 통과하고 이름의 공백이 유지된다
    assert candidate == "report.pdf "


def test_the_blocked_message_uses_the_lowercase_extension() -> None:
    """차단 문구의 확장자는 소문자다.

    테스트 코드: AT-009
    """
    # when·then: "SETUP.MSI"이면 ".msi" 문구다
    with raises_with(InvalidValueError, "실행·설치 파일(.msi)은 업로드할 수 없습니다."):
        _check("SETUP.MSI")


def test_a_nul_in_the_description_is_rejected() -> None:
    """설명에 NUL이 있으면 거절된다.

    테스트 코드: AT-007
    """
    # when·then: 설명 "a\x00b"이면 NUL 오류다
    with pytest.raises(InvalidValueError, match="NUL"):
        _check("a.pdf", "a\x00b")
