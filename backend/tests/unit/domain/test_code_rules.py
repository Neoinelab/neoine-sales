"""코드 이름 정규화·중복·key 생성·순서 규칙 (CD-011~013, CD-015, CD-019, CD-031~035).

generate_key(name, used_keys)의 used_keys는 이미 쓰는 key 문자열의 모음(Collection[str])이다.
reorder(codes, ordered_ids, now)는 코드 목록을 새 순서로 돌려주며, order가 바뀐 코드만
updated_at을 now로 바꾼다.
"""

from typing import TYPE_CHECKING

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
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.domain.code.entities import Code

REORDER_MESSAGE = "순서 목록이 올바르지 않습니다."


# --- normalize_code_name ---


def test_normalize_code_name_trims_surrounding_spaces() -> None:
    """이름의 앞뒤 공백은 지운다.

    테스트 코드: CD-011
    """
    # when: 앞뒤 공백이 있는 이름을 정리한다
    name = normalize_code_name("  보류  ")

    # then: 공백이 지워진다
    assert name == "보류"


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"], ids=["empty", "spaces", "tab-newline"])
def test_normalize_code_name_rejects_blank(raw: str) -> None:
    """빈 이름·공백뿐인 이름은 "이름을 입력하세요."로 거절한다.

    테스트 코드: CD-013
    """
    # when: 빈 이름을 정리한다
    with pytest.raises(InvalidValueError) as raised:
        normalize_code_name(raw)

    # then: 안내 문구가 난다
    assert str(raised.value) == "이름을 입력하세요."


def test_normalize_code_name_accepts_50_characters_after_trimming() -> None:
    """공백을 지운 뒤 50자인 이름은 허용한다.

    테스트 코드: CD-012
    """
    # when: 공백으로 감싼 50자 이름을 정리한다
    name = normalize_code_name(f" {'가' * 50} ")

    # then: 50자 이름이 된다
    assert name == "가" * 50


def test_normalize_code_name_rejects_51_characters() -> None:
    """51자 이름은 자르지 않고 거절한다.

    테스트 코드: CD-012
    """
    # when: 51자 이름을 정리한다
    with pytest.raises(InvalidValueError) as raised:
        normalize_code_name("가" * 51)

    # then: 50자 이내 안내 문구가 난다
    assert str(raised.value) == "이름은 50자 이내로 입력하세요."


# --- ensure_unique_name ---


def test_unique_code_name_is_case_insensitive() -> None:
    """같은 종류의 이름은 대소문자를 무시하고 중복이다.

    테스트 코드: CD-015
    """
    # given: Best가 있는 Forecast 목록
    siblings = [make_code(CodeKind.FORECAST, key="best", name="Best")]

    # when: "best"가 유일한지 확인한다
    with pytest.raises(DuplicateCodeNameError):
        ensure_unique_name(siblings, "best")

    # then: 중복 오류가 난다(위 with 블록)


def test_unique_code_name_accepts_a_different_name() -> None:
    """다른 이름은 통과한다."""
    # given: Best가 있는 Forecast 목록
    siblings = [make_code(CodeKind.FORECAST, key="best", name="Best")]

    # when: 다른 이름이 유일한지 확인한다
    ensure_unique_name(siblings, "Best Case")

    # then: 오류 없이 끝난다


def test_unique_code_name_ignores_the_code_itself() -> None:
    """자기 자신과만 겹치는 이름(대소문자만 바꿈)은 허용한다.

    테스트 코드: CD-027
    """
    # given: Best 하나
    best = make_code(CodeKind.FORECAST, key="best", name="Best")

    # when: 자기 자신을 제외하고 "BEST"가 유일한지 확인한다
    ensure_unique_name([best], "BEST", self_id=best.id)

    # then: 오류 없이 끝난다


def test_unique_code_name_still_conflicts_with_other_codes_when_self_is_given() -> None:
    """자기 자신을 제외해도 다른 코드와 겹치면 중복이다.

    테스트 코드: CD-028
    """
    # given: Best와 Commit
    best = make_code(CodeKind.FORECAST, key="best", name="Best")
    commit = make_code(CodeKind.FORECAST, key="commit", name="Commit")

    # when: Best의 이름을 "commit"으로 바꿀 수 있는지 확인한다
    with pytest.raises(DuplicateCodeNameError):
        ensure_unique_name([best, commit], "commit", self_id=best.id)

    # then: 중복 오류가 난다(위 with 블록)


# --- generate_key ---


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Most Likely 2", "most_likely_2"),
        ("Final  Review!!", "final_review"),
        ("--Deal Close--", "deal_close"),
        ("  Poc / Review!! ", "poc_review"),
        ("POC 준비", "poc"),
        ("POC준비 Stage", "poc_stage"),
        ("PIPELINE", "pipeline"),
    ],
)
def test_generate_key_slugifies_the_name(name: str, expected: str) -> None:
    """key는 소문자로 바꾸고 영문·숫자가 아닌 묶음을 밑줄 하나로 바꾸며 앞뒤 밑줄을 지운다.

    테스트 코드: CD-019
    """
    # when: 이름에서 key를 만든다
    key = generate_key(name, set())

    # then: 정리된 key다
    assert key == CodeKey(expected)


def test_generate_key_without_ascii_uses_code_sequence() -> None:
    """영문·숫자가 없는 이름은 code_1을 쓴다.

    테스트 코드: CD-017
    """
    # when: 한글뿐인 이름에서 key를 만든다
    key = generate_key("보류", set())

    # then: code_1이다
    assert key == CodeKey("code_1")


def test_generate_key_without_ascii_skips_used_sequence_numbers() -> None:
    """code_N은 쓰지 않은 가장 작은 번호를 받는다.

    테스트 코드: CD-017
    """
    # when: 영문 없는 이름에서 key를 만든다 (전제: code_1, code_2를 이미 쓴다)
    actual = generate_key("보류", {"code_1"})
    # then: 쓰지 않은 가장 작은 번호다
    assert actual == CodeKey("code_2")
    assert generate_key("검토", {"code_1", "code_2"}) == CodeKey("code_3")


def test_generate_key_appends_suffix_on_collision() -> None:
    """같은 key가 있으면 _2를 붙인다.

    테스트 코드: CD-018
    """
    # when: 같은 key가 나오는 이름에서 key를 만든다 (전제: best를 이미 쓴다)
    key = generate_key("best", {"best"})

    # then: best_2다
    assert key == CodeKey("best_2")


def test_generate_key_keeps_counting_suffixes() -> None:
    """같은 key가 계속 겹치면 _3, _4로 센다.

    테스트 코드: CD-018
    """
    # when: 같은 key가 나오는 이름에서 key를 만든다 (전제: best, best_2를 이미 쓴다)
    key = generate_key("best", {"best", "best_2"})

    # then: best_3이다
    assert key == CodeKey("best_3")


@pytest.mark.parametrize(
    ("name", "expected"),
    [("2nd", "c_2nd"), ("2024", "c_2024"), ("2026 Plan", "c_2026_plan"), ("123", "c_123")],
)
def test_generate_key_prefixes_a_leading_digit(name: str, expected: str) -> None:
    """숫자로 시작하는 key는 앞에 c_를 붙인다.

    테스트 코드: CD-019
    """
    # when: 숫자로 시작하는 이름에서 key를 만든다
    key = generate_key(name, set())

    # then: c_가 붙는다
    assert key == CodeKey(expected)


def test_generate_key_never_exceeds_50_characters_even_with_a_collision() -> None:
    """key는 50자를 넘지 않고, 충돌하면 앞부분을 잘라 접미사를 붙인다.

    테스트 코드: CD-019
    """
    # given: 영문 50자 key를 이미 쓴다
    used = {"a" * 50}

    # when: 영문 60자 이름에서 key를 만든다
    key = generate_key("A" * 60, used)

    # then: 앞 48자 + "_2"(50자)이다
    assert key.value == "a" * 48 + "_2"
    assert generate_key("A" * 60, set()).value == "a" * 50


# --- reorder ---


def _three_codes() -> list[Code]:
    return [
        make_code(CodeKind.STATUS, key=f"k{n}", name=f"코드{n}", order=n, now=NOW)
        for n in (1, 2, 3)
    ]


def test_reorder_renumbers_from_one_in_the_given_order() -> None:
    """보낸 id 순서대로 order를 1부터 다시 매긴다.

    테스트 코드: CD-031
    """
    # given: 코드 3개
    first, second, third = _three_codes()

    # when: 셋째, 첫째, 둘째 순서로 재배열한다
    result = reorder([first, second, third], [third.id, first.id, second.id], later(60))

    # then: 1, 2, 3으로 다시 매겨진다
    assert [(c.id, c.order) for c in result] == [(third.id, 1), (first.id, 2), (second.id, 3)]


def test_reorder_touches_only_the_codes_whose_order_changed() -> None:
    """order가 바뀐 코드만 변경 시각을 갱신한다.

    테스트 코드: CD-032
    """
    # given: 코드 3개
    first, second, third = _three_codes()

    # when: 뒤의 둘만 자리를 바꾼다
    result = {
        c.id: c for c in reorder([first, second, third], [first.id, third.id, second.id], later(60))
    }

    # then: 바뀌지 않은 첫째는 원래 시각이고 나머지 둘은 새 시각이다
    assert result[first.id].updated_at == NOW
    assert result[second.id].updated_at == later(60)
    assert result[third.id].updated_at == later(60)


def test_reorder_closes_gaps_left_by_deleted_codes() -> None:
    """삭제로 생긴 빈 번호를 메운다.

    테스트 코드: CD-034
    """
    # given: order가 1, 3, 7인 코드 3개
    first = make_code(CodeKind.STATUS, key="k1", order=1)
    second = make_code(CodeKind.STATUS, key="k2", order=3)
    third = make_code(CodeKind.STATUS, key="k3", order=7)

    # when: 지금 순서대로 재배열한다
    result = reorder([first, second, third], [first.id, second.id, third.id], later(60))

    # then: 1, 2, 3이다
    assert [c.order for c in result] == [1, 2, 3]


def test_reorder_rejects_a_list_missing_a_code() -> None:
    """코드가 빠진 목록은 거절한다.

    테스트 코드: CD-035
    """
    # given: 코드 3개
    first, second, third = _three_codes()

    # when: 둘만 담아 재배열한다
    with pytest.raises(InvalidValueError) as raised:
        reorder([first, second, third], [first.id, second.id], later(60))

    # then: 순서 목록 오류 문구다
    assert str(raised.value) == REORDER_MESSAGE


def test_reorder_rejects_a_list_with_a_duplicate_id() -> None:
    """같은 id가 중복된 목록은 거절한다.

    테스트 코드: CD-035
    """
    # given: 코드 3개
    first, second, third = _three_codes()

    # when: 첫째 id를 두 번 담아 재배열한다
    with pytest.raises(InvalidValueError) as raised:
        reorder([first, second, third], [first.id, first.id, second.id, third.id], later(60))

    # then: 순서 목록 오류 문구다
    assert str(raised.value) == REORDER_MESSAGE


def test_reorder_rejects_an_unknown_or_foreign_id() -> None:
    """없는 id(또는 다른 종류의 id)가 섞인 목록은 거절한다.

    테스트 코드: CD-035
    """
    # given: 코드 3개
    first, second, third = _three_codes()

    # when: 셋째 대신 모르는 id를 담아 재배열한다
    with pytest.raises(InvalidValueError) as raised:
        reorder([first, second, third], [first.id, second.id, CodeId(new_id())], later(60))

    # then: 순서 목록 오류 문구다
    assert str(raised.value) == REORDER_MESSAGE


def test_reorder_rejects_an_empty_list_for_existing_codes() -> None:
    """빈 목록은 기존 코드가 있으면 거절한다.

    테스트 코드: CD-035
    """
    # given: 코드 3개
    codes = _three_codes()

    # when: 빈 목록으로 재배열한다
    with pytest.raises(InvalidValueError) as raised:
        reorder(codes, [], later(60))

    # then: 순서 목록 오류 문구다
    assert str(raised.value) == REORDER_MESSAGE
