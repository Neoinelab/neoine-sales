"""한국어 조사 도우미(R-4): 프런트 `shared/model/text.ts`와 같은 받침 규칙(`text.test.ts` 사례)."""

import pytest
from app.domain.common.korean import with_ga, with_ro, with_wa


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("계약완료", "계약완료로"),  # 받침 없음
        ("가격협상", "가격협상으로"),  # 받침 ㅇ
        ("기술평가", "기술평가로"),
        ("서울", "서울로"),  # ㄹ 받침은 '로'
        ("Won", "Won으로"),  # 영문 끝 글자 n = 받침 있음
        ("Best", "Best로"),
        ("Pipeline", "Pipeline로"),
        ("Help", "Help으로"),  # 끝 글자 p = 받침 있음
        ("2", "2로"),  # 숫자: 0 1 3 6 7 8만 받침
        ("3", "3으로"),
        ("10", "10으로"),
    ],
)
def test_with_ro_follows_the_final_sound_rule(text: str, expected: str) -> None:
    assert with_ro(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("계약완료", "계약완료가"),
        ("가격협상", "가격협상이"),
        ("Won", "Won이"),
        ("Best", "Best가"),
    ],
)
def test_with_ga_picks_ga_or_i(text: str, expected: str) -> None:
    assert with_ga(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Status 계약완료", "Status 계약완료와"),
        ("Forecast Won", "Forecast Won과"),
        ("가격협상", "가격협상과"),
        ("Best", "Best와"),
    ],
)
def test_with_wa_picks_wa_or_gwa(text: str, expected: str) -> None:
    assert with_wa(text) == expected


def test_josa_of_an_empty_text_is_the_no_final_sound_form() -> None:
    assert (with_ro(""), with_ga(""), with_wa("")) == ("로", "가", "와")
