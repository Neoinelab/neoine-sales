"""StoragePath 값 객체(P2b AC-02·06): 절대 POSIX 경로 하나를 검증하고 정규화한다."""

import pytest
from app.domain.storage.path import (
    PATH_NOT_ABSOLUTE,
    PATH_NOT_WRITABLE,
    PATH_TOO_LONG,
    STORAGE_PATH_MAX,
    StoragePath,
)

from app.domain.common.errors import InvalidValueError

NOT_ABSOLUTE = "절대 경로를 입력하세요."
TOO_LONG = "저장 경로는 1024자 이내로 입력하세요."
NOT_WRITABLE = "해당 위치에 쓸 수 없습니다."


def test_the_messages_are_the_fixed_user_facing_sentences() -> None:
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
    assert StoragePath.parse(raw).value == expected


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
    with pytest.raises(InvalidValueError) as caught:
        StoragePath.parse(raw)

    assert str(caught.value) == NOT_ABSOLUTE


def test_parse_accepts_exactly_the_maximum_length() -> None:
    raw = "/" + "a" * (STORAGE_PATH_MAX - 1)

    assert StoragePath.parse(raw).value == raw


def test_parse_rejects_one_character_over_the_maximum_length() -> None:
    raw = "/" + "a" * STORAGE_PATH_MAX

    with pytest.raises(InvalidValueError) as caught:
        StoragePath.parse(raw)

    assert str(caught.value) == TOO_LONG


def test_the_length_is_measured_in_characters_not_bytes() -> None:
    raw = "/" + "가" * (STORAGE_PATH_MAX - 1)

    assert StoragePath.parse(raw).value == raw


def test_the_length_is_measured_after_normalization() -> None:
    padded = "  /" + "a" * (STORAGE_PATH_MAX - 1) + "///  "

    assert StoragePath.parse(padded).value == "/" + "a" * (STORAGE_PATH_MAX - 1)


@pytest.mark.parametrize("raw", ["/data/\x00files", "\x00", "/data/files\x00", "relative\x00"])
def test_parse_rejects_nul_characters_before_any_other_rule(raw: str) -> None:
    with pytest.raises(InvalidValueError) as caught:
        StoragePath.parse(raw)

    assert "NUL" in str(caught.value)


def test_parse_is_idempotent_on_its_own_output() -> None:
    once = StoragePath.parse(" /data//files/ ")

    assert StoragePath.parse(once.value) == once


def test_equal_paths_compare_equal_and_are_hashable() -> None:
    assert StoragePath.parse("/data/files") == StoragePath.parse(" /data//files/ ")
    assert len({StoragePath.parse("/data/files"), StoragePath.parse("/data/files/")}) == 1
