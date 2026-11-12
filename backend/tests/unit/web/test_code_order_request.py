"""코드 순서 요청(CD-036): `ordered_ids`는 JSON 정수(1 이상 2^53-1 이하)의 배열이다."""

import pytest
from pydantic import ValidationError

from app.domain.code.values import CodeKind
from app.web.schemas.code import CodeOrderRequest
from tests.support.ids import MAX_ID


def test_ordered_ids_accept_integers_in_the_given_order() -> None:
    """정수 id 목록은 보낸 순서 그대로 받아들인다.

    테스트 코드: CD-036
    """
    # when: 정수 목록으로 요청을 만든다
    request = CodeOrderRequest(kind=CodeKind.STATUS, ordered_ids=[3, 1, 2])

    # then: 순서가 그대로다
    assert request.ids() == [3, 1, 2]


def test_the_largest_allowed_id_is_accepted() -> None:
    """허용되는 가장 큰 id(2^53-1)도 받아들인다.

    테스트 코드: CD-036
    """
    # when·then: 최대 id로 요청을 만들면 그대로 담긴다
    assert CodeOrderRequest(kind=CodeKind.STATUS, ordered_ids=[MAX_ID]).ids() == [MAX_ID]


@pytest.mark.parametrize("bad", ["1", True, 1.0, 0, -1, MAX_ID + 1])
def test_ordered_ids_must_be_integers(bad: object) -> None:
    """문자열·실수·불리언·범위 밖 숫자는 요청 검증 오류다.

    테스트 코드: CD-036
    """
    # when: 둘째 자리에 정수가 아닌 값을 담는다
    with pytest.raises(ValidationError) as caught:
        CodeOrderRequest(kind=CodeKind.STATUS, ordered_ids=[1, bad])

    # then: 그 자리(ordered_ids[1])의 오류다
    assert [e["loc"] for e in caught.value.errors()] == [("ordered_ids", 1)]


def test_a_list_of_numeric_strings_is_rejected() -> None:
    """숫자 문자열 목록은 거절한다.

    테스트 코드: CD-036
    """
    # when: 숫자 문자열 목록으로 요청을 검증한다
    with pytest.raises(ValidationError):
        CodeOrderRequest.model_validate({"kind": "status", "ordered_ids": ["1", "2"]})

    # then: 검증 오류가 난다(위 with 블록)
