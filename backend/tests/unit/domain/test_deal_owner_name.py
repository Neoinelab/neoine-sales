"""담당자 이름 검색(DL-R39)의 도메인 규칙: 상수와 퇴사자 표기(`이름(퇴사)`) 해석."""

import pytest
from app.domain.deal.owner_name import OWNER_NAME_MAX, RESIGNED_SUFFIX, resigned_owner_name


def test_the_limits_are_100_characters_and_the_halfwidth_resigned_suffix() -> None:
    """담당자 이름 최대 길이는 100자이고 퇴사 표기는 반각 괄호의 "(퇴사)"다."""
    # when·then: 상수 값
    assert OWNER_NAME_MAX == 100
    assert RESIGNED_SUFFIX == "(퇴사)"


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("강영업(퇴사)", "강영업"),
        ("Bob(퇴사)", "Bob"),
        ("강 영업(퇴사)", "강 영업"),
        (
            "강영업 (퇴사)",
            "강영업 ",
        ),  # 앞 글자를 그대로 돌려준다(띄어 쓴 값은 이름과 달라 맞지 않는다)
    ],
)
def test_text_ending_with_the_suffix_returns_the_part_before_it(text: str, name: str) -> None:
    """ "(퇴사)"로 끝나는 글자는 그 앞 글자 전체를 이름으로 돌려준다."""
    # when: 퇴사자 이름을 해석한다
    actual = resigned_owner_name(text)
    # then: 접미사를 뺀 앞 글자 전체다
    assert actual == name


@pytest.mark.parametrize(
    "text",
    [
        "강영업",
        "강영업(퇴",
        f"강영업{chr(0xFF08)}퇴사{chr(0xFF09)}",
        "강영업(퇴사) ",
        "강영업(퇴사)x",
        "(퇴사",
        "",
    ],
)
def test_text_without_the_exact_suffix_at_the_end_is_not_a_resigned_name(text: str) -> None:
    """반각 "(퇴사)"로 끝나지 않는 글자(덜 친 값·전각 괄호·뒤에 글자)는 퇴사자 표기가 아니다."""
    # when: 해석한다
    actual = resigned_owner_name(text)
    # then: None이다
    assert actual is None
