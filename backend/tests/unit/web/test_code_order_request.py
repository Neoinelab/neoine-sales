"""코드 순서 요청(AC-14): `ordered_ids`는 JSON 정수(1 이상 2^53-1 이하)의 배열이다."""

import pytest
from pydantic import ValidationError

from app.domain.code.values import CodeKind
from app.web.schemas.code import CodeOrderRequest
from tests.support.ids import MAX_ID


def test_ordered_ids_accept_integers_in_the_given_order() -> None:
    request = CodeOrderRequest(kind=CodeKind.STATUS, ordered_ids=[3, 1, 2])

    assert request.ids() == [3, 1, 2]


def test_the_largest_allowed_id_is_accepted() -> None:
    assert CodeOrderRequest(kind=CodeKind.STATUS, ordered_ids=[MAX_ID]).ids() == [MAX_ID]


@pytest.mark.parametrize("bad", ["1", True, 1.0, 0, -1, MAX_ID + 1])
def test_ordered_ids_must_be_integers(bad: object) -> None:
    with pytest.raises(ValidationError) as caught:
        CodeOrderRequest(kind=CodeKind.STATUS, ordered_ids=[1, bad])

    assert [e["loc"] for e in caught.value.errors()] == [("ordered_ids", 1)]


def test_a_list_of_numeric_strings_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CodeOrderRequest.model_validate({"kind": "status", "ordered_ids": ["1", "2"]})
