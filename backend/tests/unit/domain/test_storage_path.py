"""StoragePath 값 객체: 절대 POSIX 경로 하나를 검증하고 정규화한다."""

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.storage.path import (
    PATH_NOT_ABSOLUTE,
    PATH_NOT_WRITABLE,
    PATH_TOO_LONG,
    STORAGE_PATH_MAX,
    StoragePath,
)

NOT_ABSOLUTE = "절대 경로를 입력하세요."
TOO_LONG = "저장 경로는 1024자 이내로 입력하세요."
NOT_WRITABLE = "해당 위치에 쓸 수 없습니다."


def test_the_messages_are_the_fixed_user_facing_sentences() -> None:
    """경로 오류 문구는 고정 문장이다.

    테스트 코드: IN-047, IN-048, IN-049
    """
    # when·then: 문구 상수를 읽는다 → 절대 경로·1024자·NUL 문구가 문서와 같다
    assert PATH_NOT_ABSOLUTE == NOT_ABSOLUTE
    assert PATH_TOO_LONG == TOO_LONG
    assert PATH_NOT_WRITABLE == NOT_WRITABLE
    assert STORAGE_PATH_MAX == 1024


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/data/neoine-sales/files", "/data/neoine-sales/files"),
        ("  /data/files  ", "/data/files"),
        ("\t/data/files\n", "/data/files"),
        ("/data//files", "/data/files"),
        ("/data///files//", "/data/files"),
        ("/data/files/", "/data/files"),
        ("/", "/"),
        ("/var/lib/neoine-sales/files", "/var/lib/neoine-sales/files"),
        ("/데이터/영업 파일", "/데이터/영업 파일"),
        ("/a/..b/c..", "/a/..b/c.."),
    ],
)
def test_parse_trims_and_normalizes_slashes(raw: str, expected: str) -> None:
    """앞뒤 공백·중복 슬래시·점 조각·끝 슬래시를 정리한다.

    테스트 코드: IN-046
    """
    # when: 여러 형태의 경로를 해석한다
    value = StoragePath.parse(raw).value
    # then: 정규화된 경로가 나온다
    assert value == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "data/files",
        "files",
        "./files",
        "~/files",
        "C:\\files",
        "/a/../b",
        "/..",
        "/a/..",
        "/a/b/../..",
    ],
)
def test_parse_rejects_empty_relative_and_dot_dot_paths(raw: str) -> None:
    """빈 값·상대 경로·..가 있는 경로는 '절대 경로를 입력하세요.'로 거절한다.

    테스트 코드: IN-047
    """
    # when: 그런 경로를 해석한다
    with pytest.raises(InvalidValueError) as caught:
        StoragePath.parse(raw)

    # then: InvalidValueError다
    assert str(caught.value) == NOT_ABSOLUTE


def test_parse_accepts_exactly_the_maximum_length() -> None:
    """정규화한 경로가 1024자면 받는다.

    테스트 코드: IN-048
    """
    # when: 1024자 경로를 해석한다
    raw = "/" + "a" * (STORAGE_PATH_MAX - 1)

    # then: 받아진다
    assert StoragePath.parse(raw).value == raw


def test_parse_rejects_one_character_over_the_maximum_length() -> None:
    """1025자는 '저장 경로는 1024자 이내로 입력하세요.'로 거절한다.

    테스트 코드: IN-048
    """
    # when: 1025자 경로를 해석한다
    raw = "/" + "a" * STORAGE_PATH_MAX

    with pytest.raises(InvalidValueError) as caught:
        StoragePath.parse(raw)

    # then: InvalidValueError다
    assert str(caught.value) == TOO_LONG


def test_the_length_is_measured_in_characters_not_bytes() -> None:
    """길이는 바이트가 아니라 문자 수로 센다.

    테스트 코드: IN-048
    """
    # when: 한글 1024자 경로를 해석한다
    raw = "/" + "가" * (STORAGE_PATH_MAX - 1)

    # then: 받아진다
    assert StoragePath.parse(raw).value == raw


def test_the_length_is_measured_after_normalization() -> None:
    """길이는 정규화한 뒤의 값으로 센다.

    테스트 코드: IN-048
    """
    # when: 중복 슬래시를 빼면 1024자인 경로를 해석한다
    padded = "  /" + "a" * (STORAGE_PATH_MAX - 1) + "///  "

    # then: 받아진다
    assert StoragePath.parse(padded).value == "/" + "a" * (STORAGE_PATH_MAX - 1)


@pytest.mark.parametrize("raw", ["/data/\x00files", "\x00", "/data/files\x00", "relative\x00"])
def test_parse_rejects_nul_characters_before_any_other_rule(raw: str) -> None:
    """NUL이 든 경로는 다른 규칙보다 먼저 NUL 문구로 거절한다.

    테스트 코드: IN-049
    """
    # when: NUL이 든 경로(상대 경로 포함)를 해석한다
    with pytest.raises(InvalidValueError) as caught:
        StoragePath.parse(raw)

    # then: NUL 문구의 InvalidValueError다
    assert "NUL" in str(caught.value)


def test_parse_is_idempotent_on_its_own_output() -> None:
    """정규화한 값을 다시 넣어도 같다.

    테스트 코드: IN-046
    """
    # when: 정규화 결과를 다시 해석한다
    once = StoragePath.parse(" /data//files/ ")

    # then: 같은 경로다
    assert StoragePath.parse(once.value) == once


def test_equal_paths_compare_equal_and_are_hashable() -> None:
    """같은 경로는 같고 해시할 수 있다."""
    # when: 같은 경로 둘을 비교한다
    actual = StoragePath.parse("/data/files")
    # then: 같다
    assert actual == StoragePath.parse(" /data//files/ ")
    assert len({StoragePath.parse("/data/files"), StoragePath.parse("/data/files/")}) == 1
