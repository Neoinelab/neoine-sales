"""CodeInUseError.unit은 "Deal" 또는 "Action"만 쓴다(P2 이월 Q6-e): 타입 표기를 Literal로 좁힌다."""

from typing import Literal, get_type_hints

from app.domain.code.errors import CodeInUseError


def test_unit_parameter_is_a_closed_set_of_deal_and_action() -> None:
    """단위 표기는 "Deal" 또는 "Action"만 허용하는 Literal이다."""
    # when: 생성자 타입 힌트를 읽는다
    hints = get_type_hints(CodeInUseError.__init__)

    # then: Deal·Action 두 값이다
    assert hints["unit"] == Literal["Deal", "Action"]


def test_the_message_names_the_unit_and_the_count() -> None:
    """문구에 단위와 건수가 들어간다.

    테스트 코드: CD-040
    """
    # when·then: 오류 문구를 만들면 Deal 3건·Action 2건 문구다
    assert str(CodeInUseError(3)) == "사용 중인 코드는 삭제할 수 없습니다. (Deal 3건)"
    assert str(CodeInUseError(2, "Action")) == "사용 중인 코드는 삭제할 수 없습니다. (Action 2건)"
