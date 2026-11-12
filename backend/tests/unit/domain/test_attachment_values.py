"""첨부 값과 한도: 상수·문구, 확장자 판정, 설명 검증, 스트리밍 한도."""

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
    """한도 값과 위반 문구는 문서의 고정 값이다.

    테스트 코드: AT-006
    """
    # when·then: 100MB·설명 100자·이름 255자와 네 가지 문구가 고정 값이다
    assert MAX_FILE_BYTES == 104_857_600
    assert (DESCRIPTION_MAX, FILE_NAME_MAX) == (100, 255)
    assert NO_FILE == "업로드할 파일을 선택하세요."
    assert DESCRIPTION_TOO_LONG == "설명은 100자 이내로 입력하세요."
    assert FILE_TOO_LARGE == "파일 크기가 100MB를 초과합니다. (최대 100MB)"
    assert INVALID_FILE_NAME == "사용할 수 없는 파일 이름입니다."


def test_blocked_extensions_are_the_prd_list_plus_the_eleven_decided_ones() -> None:
    """차단 확장자는 PRD 13개 + 결정한 11개 = 24개다.

    테스트 코드: AT-009
    """
    # when·then: 목록이 24개 집합과 같다
    assert frozenset(PRD_BLOCKED + EXTRA_BLOCKED) == BLOCKED_EXTENSIONS
    assert len(BLOCKED_EXTENSIONS) == 24


@pytest.mark.parametrize("extension", ["zip", "gz", "pdf", "txt", "docx", "exe2", ""])
def test_ordinary_and_archive_extensions_are_not_blocked(extension: str) -> None:
    """일반·압축 확장자는 차단 목록에 없다.

    테스트 코드: AT-009
    """
    # when·then: 차단 목록에 들어 있지 않다
    assert extension not in BLOCKED_EXTENSIONS


def test_blocked_message_names_the_extension() -> None:
    """차단 문구는 확장자를 이름으로 담는다.

    테스트 코드: AT-009
    """
    # when: 차단 문구를 만든다
    message = blocked_message("exe")

    # then: 확장자가 든 문구다
    assert message == "실행·설치 파일(.exe)은 업로드할 수 없습니다."


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
    """확장자 판정은 마지막 확장자를 소문자로 돌려준다.

    테스트 코드: AT-009
    """
    # when: 확장자를 판정한다
    extension = extension_of(name)

    # then: 마지막 확장자를 소문자로 돌려준다
    assert extension == expected


@pytest.mark.parametrize(
    "name",
    [
        "setup.exe ",  # ASCII 공백
        "setup.exe\u3000",  # 전각 공백
        "setup.exe\u00a0",  # NBSP
        "setup.exe\u2003",  # em space
        "setup.exe\t",
        "setup.exe .",
        "setup.exe.\u3000 .",
    ],
)
def test_extension_of_ignores_trailing_unicode_whitespace_and_dots(name: str) -> None:
    """끝의 유니코드 공백·점은 걷고 확장자를 판정한다.

    테스트 코드: AT-009
    """
    # when: 끝에 공백·점이 붙은 이름의 확장자를 판정한다
    extension = extension_of(name)

    # then: 확장자는 "exe"다
    assert extension == "exe"


def test_on_exists_has_the_three_wire_values() -> None:
    """on_exists는 ask·replace·skip 세 값이다.

    테스트 코드: AT-012
    """
    # when·then: 값 목록이 세 개이고 "ask"가 ASK로 해석된다
    assert [m.value for m in OnExists] == ["ask", "replace", "skip"]
    assert OnExists("ask") is OnExists.ASK


def test_on_exists_rejects_an_unknown_value() -> None:
    """알 수 없는 on_exists 값은 거절된다.

    테스트 코드: AT-012
    """
    # when·then: "overwrite"를 해석하면 오류다
    with pytest.raises(ValueError, match="overwrite"):
        OnExists("overwrite")


def test_parse_description_trims_and_keeps_inner_whitespace() -> None:
    """설명은 앞뒤 공백만 지우고 안쪽 공백은 둔다.

    테스트 코드: AT-001
    """
    # when: 앞뒤 공백이 있는 설명을 해석한다
    description = parse_description("  견적서  최종 \n")

    # then: 안쪽 공백은 유지된 채 앞뒤가 지워진다
    assert description == "견적서  최종"


def test_parse_description_of_blank_text_is_empty() -> None:
    """공백뿐인 설명은 빈 문자열이다.

    테스트 코드: AT-002
    """
    # when: 공백뿐인 설명을 해석한다
    description = parse_description(" \t ")

    # then: 빈 문자열이다
    assert description == ""


def test_parse_description_accepts_exactly_100_code_points() -> None:
    """설명은 정확히 100 코드 포인트까지 받아들인다.

    테스트 코드: AT-005
    """
    # when: 이모지 100개 설명을 해석한다
    description = parse_description("😀" * 100)

    # then: 그대로 받아들여진다
    assert description == "😀" * 100


def test_parse_description_counts_code_points_after_trimming() -> None:
    """설명 길이는 앞뒤 공백을 지운 뒤 센다.

    테스트 코드: AT-005
    """
    # given: 앞뒤 공백이 붙은 100자 설명
    padded = "  " + "가" * 100 + "  "

    # when: 앞뒤 공백이 붙은 100자 설명을 해석한다
    description = parse_description(padded)

    # then: 공백이 지워진 100자다
    assert description == "가" * 100


def test_parse_description_rejects_101_code_points() -> None:
    """설명이 101 코드 포인트면 거절된다.

    테스트 코드: AT-006
    """
    # when·then: 이모지 101개를 해석하면 설명 문구 오류다
    with raises_with(InvalidValueError, DESCRIPTION_TOO_LONG):
        parse_description("😀" * 101)


def test_parse_description_rejects_nul_even_when_otherwise_valid() -> None:
    """다른 위반이 없어도 NUL이 있으면 설명이 거절된다.

    테스트 코드: AT-007
    """
    # when·then: NUL이 든 설명을 해석하면 NUL 오류다
    with pytest.raises(InvalidValueError, match="NUL"):
        parse_description("견적\x00서")


def test_ensure_within_limit_allows_zero_and_the_exact_maximum() -> None:
    """0바이트와 정확히 100MB는 한도 안이다.

    테스트 코드: AT-005
    """
    # when·then: 두 크기 모두 오류 없이 통과한다
    ensure_within_limit(0)
    ensure_within_limit(MAX_FILE_BYTES)


def test_ensure_within_limit_rejects_one_byte_over() -> None:
    """한도보다 1바이트 크면 거절된다.

    테스트 코드: AT-006
    """
    # when·then: 100MB+1바이트이면 크기 문구 오류다
    with raises_with(InvalidValueError, FILE_TOO_LARGE):
        ensure_within_limit(MAX_FILE_BYTES + 1)
