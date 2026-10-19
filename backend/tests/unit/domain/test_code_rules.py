"""코드 이름 정규화·중복·key 생성·순서 규칙 (AC-03·04·06).

generate_key(name, used_keys)의 used_keys는 이미 쓰는 key 문자열의 모음(Collection[str])이다.
reorder(codes, ordered_ids, now)는 코드 목록을 새 순서로 돌려주며, order가 바뀐 코드만
updated_at을 now로 바꾼다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.domain.code.errors import DuplicateCodeNameError
from app.domain.code.rules import (
    ensure_unique_name,
    generate_key,
    normalize_code_name,
    reorder,
)
from app.domain.code.values import CodeId, CodeKey, CodeKind
from app.domain.common.errors import InvalidValueError
from tests.factories import NOW, later
from tests.factories_catalog import make_code

if TYPE_CHECKING:
    from app.domain.code.entities import Code

REORDER_MESSAGE = "순서 목록이 올바르지 않습니다."


# --- normalize_code_name (AC-04) ---


def test_normalize_code_name_trims_surrounding_spaces() -> None:
    assert normalize_code_name("  보류  ") == "보류"


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"], ids=["empty", "spaces", "tab-newline"])
def test_normalize_code_name_rejects_blank(raw: str) -> None:
    with pytest.raises(InvalidValueError) as raised:
        normalize_code_name(raw)

    assert str(raised.value) == "이름을 입력하세요."


def test_normalize_code_name_accepts_50_characters_after_trimming() -> None:
    assert normalize_code_name(f" {'가' * 50} ") == "가" * 50


def test_normalize_code_name_rejects_51_characters() -> None:
    with pytest.raises(InvalidValueError):
        normalize_code_name("가" * 51)


# --- ensure_unique_name (AC-04) ---


def test_unique_code_name_is_case_insensitive() -> None:
    siblings = [make_code(CodeKind.FORECAST, key="best", name="Best")]

    with pytest.raises(DuplicateCodeNameError):
        ensure_unique_name(siblings, "best")


def test_unique_code_name_accepts_a_different_name() -> None:
    siblings = [make_code(CodeKind.FORECAST, key="best", name="Best")]

    ensure_unique_name(siblings, "Best Case")


def test_unique_code_name_ignores_the_code_itself() -> None:
    best = make_code(CodeKind.FORECAST, key="best", name="Best")

    ensure_unique_name([best], "BEST", self_id=best.id)


def test_unique_code_name_still_conflicts_with_other_codes_when_self_is_given() -> None:
    best = make_code(CodeKind.FORECAST, key="best", name="Best")
    commit = make_code(CodeKind.FORECAST, key="commit", name="Commit")

    with pytest.raises(DuplicateCodeNameError):
        ensure_unique_name([best, commit], "commit", self_id=best.id)


# --- generate_key (AC-03) ---


def test_generate_key_slugifies_ascii_name() -> None:
    assert generate_key("Most Likely 2", set()) == CodeKey("most_likely_2")


def test_generate_key_collapses_punctuation_and_trims_underscores() -> None:
    assert generate_key("  Poc / Review!! ", set()) == CodeKey("poc_review")


def test_generate_key_ignores_non_ascii_letters_inside_the_name() -> None:
    assert generate_key("POC 준비", set()) == CodeKey("poc")


def test_generate_key_without_ascii_uses_code_sequence() -> None:
    assert generate_key("보류", set()) == CodeKey("code_1")


def test_generate_key_without_ascii_skips_used_sequence_numbers() -> None:
    assert generate_key("보류", {"code_1"}) == CodeKey("code_2")
    assert generate_key("검토", {"code_1", "code_2"}) == CodeKey("code_3")


def test_generate_key_appends_suffix_on_collision() -> None:
    assert generate_key("best", {"best"}) == CodeKey("best_2")


def test_generate_key_keeps_counting_suffixes() -> None:
    assert generate_key("best", {"best", "best_2"}) == CodeKey("best_3")


def test_generate_key_prefixes_leading_digit() -> None:
    assert generate_key("2nd", set()) == CodeKey("c_2nd")


def test_generate_key_prefixes_digit_only_name() -> None:
    assert generate_key("2024", set()) == CodeKey("c_2024")


def test_generate_key_is_lowercase() -> None:
    assert generate_key("PIPELINE", set()) == CodeKey("pipeline")


def test_generate_key_never_exceeds_50_characters_even_with_a_collision() -> None:
    used = {"a" * 50}

    key = generate_key("A" * 60, used)

    assert len(key.value) <= 50
    assert key.value not in used


# --- reorder (AC-06) ---


def _three_codes() -> list[Code]:
    return [
        make_code(CodeKind.STATUS, key=f"k{n}", name=f"코드{n}", order=n, now=NOW)
        for n in (1, 2, 3)
    ]


def test_reorder_renumbers_from_one_in_the_given_order() -> None:
    first, second, third = _three_codes()

    result = reorder([first, second, third], [third.id, first.id, second.id], later(60))

    assert [(c.id, c.order) for c in result] == [(third.id, 1), (first.id, 2), (second.id, 3)]


def test_reorder_touches_only_the_codes_whose_order_changed() -> None:
    first, second, third = _three_codes()

    result = {
        c.id: c for c in reorder([first, second, third], [first.id, third.id, second.id], later(60))
    }

    assert result[first.id].updated_at == NOW
    assert result[second.id].updated_at == later(60)
    assert result[third.id].updated_at == later(60)


def test_reorder_closes_gaps_left_by_deleted_codes() -> None:
    first = make_code(CodeKind.STATUS, key="k1", order=1)
    second = make_code(CodeKind.STATUS, key="k2", order=3)
    third = make_code(CodeKind.STATUS, key="k3", order=7)

    result = reorder([first, second, third], [first.id, second.id, third.id], later(60))

    assert [c.order for c in result] == [1, 2, 3]


def test_reorder_rejects_a_list_missing_a_code() -> None:
    first, second, third = _three_codes()

    with pytest.raises(InvalidValueError) as raised:
        reorder([first, second, third], [first.id, second.id], later(60))

    assert str(raised.value) == REORDER_MESSAGE


def test_reorder_rejects_a_list_with_a_duplicate_id() -> None:
    first, second, third = _three_codes()

    with pytest.raises(InvalidValueError) as raised:
        reorder([first, second, third], [first.id, first.id, second.id, third.id], later(60))

    assert str(raised.value) == REORDER_MESSAGE


def test_reorder_rejects_an_unknown_or_foreign_id() -> None:
    first, second, third = _three_codes()

    with pytest.raises(InvalidValueError) as raised:
        reorder([first, second, third], [first.id, second.id, CodeId(uuid4())], later(60))

    assert str(raised.value) == REORDER_MESSAGE


def test_reorder_rejects_an_empty_list_for_existing_codes() -> None:
    with pytest.raises(InvalidValueError):
        reorder(_three_codes(), [], later(60))
