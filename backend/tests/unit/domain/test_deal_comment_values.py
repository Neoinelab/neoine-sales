"""Comment 본문 규칙: `comment_body`(필수)와 `optional_comment`(선택).

공통 규칙(CM-R1): NUL 거부가 먼저, 필수인 곳만 빈 값 거부, 통과하면 앞뒤 공백만 지우고
안쪽은 그대로,
길이 상한 없음.
"""

import pytest
from app.domain.deal_comment.values import comment_body, optional_comment

from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with

BLANK = "Comment를 입력하세요."
NUL = "Comment에는 NUL 문자를 쓸 수 없습니다"


def test_body_keeps_the_inner_whitespace_and_trims_both_ends() -> None:
    """본문은 앞뒤 공백만 지우고 안쪽 줄바꿈·공백은 그대로 둔다.

    테스트 코드: CM-002
    """
    # when: 앞뒤 공백과 안쪽 줄바꿈이 있는 본문을 정규화한다
    body = comment_body("  첫 줄\n  둘째 줄  ")

    # then: 앞뒤만 지워지고 안쪽 줄바꿈과 들여쓰기는 그대로다
    assert body == "첫 줄\n  둘째 줄"


def test_body_has_no_length_limit() -> None:
    """본문에는 길이 상한이 없어 20,000자도 자르지 않는다.

    테스트 코드: CM-002
    """
    # given: 20,000자 본문
    long_text = "가" * 20_000

    # when·then: 그대로 통과한다
    assert comment_body(long_text) == long_text


@pytest.mark.parametrize("raw", ["", "   ", "  \n \t "], ids=["empty", "spaces", "mixed-blank"])
def test_blank_body_is_rejected_when_required(raw: str) -> None:
    """필수인 곳에서 비었거나 공백뿐인 본문은 거절한다.

    테스트 코드: CM-003
    """
    # when·then: 빈 본문은 입력 요청 문구로 거절된다
    with raises_with(InvalidValueError, BLANK):
        comment_body(raw)


@pytest.mark.parametrize("raw", ["가\x00나", "\x00"], ids=["inside", "only-nul"])
def test_nul_is_rejected_before_the_blank_rule(raw: str) -> None:
    """NUL 판정이 빈 값 판정보다 먼저다(NUL만 있어도 NUL 문구).

    테스트 코드: CM-004
    """
    # when·then: NUL 문구로 거절된다
    with raises_with(InvalidValueError, NUL):
        comment_body(raw)


@pytest.mark.parametrize("raw", ["", "  ", "\n\t "], ids=["empty", "spaces", "newline-tab"])
def test_optional_blank_means_no_comment(raw: str) -> None:
    """선택인 곳에서는 비었거나 공백뿐이면 오류 없이 없음(None)이다.

    테스트 코드: CM-027, CM-033
    """
    # when·then: 빈 값은 Comment를 만들지 않는 None이다
    assert optional_comment(raw) is None


def test_optional_comment_trims_and_keeps_the_inside() -> None:
    """선택 Comment도 앞뒤 공백만 지우고 안쪽은 그대로 둔다.

    테스트 코드: CM-026, CM-031
    """
    # when·then: 앞뒤 공백이 지워진 본문이 돌아온다
    assert optional_comment("  요구사항\n정리  ") == "요구사항\n정리"


def test_optional_comment_rejects_nul_even_when_otherwise_blank() -> None:
    """선택 Comment도 NUL은 거절한다(공백만 있는 값과 달리 NUL은 비었다고 보지 않는다).

    테스트 코드: CM-028, CM-035
    """
    # when·then: NUL이 있으면 NUL 문구로 거절된다
    with raises_with(InvalidValueError, NUL):
        optional_comment(" \x00 ")
