"""본문 id(`BodyId`, PL-024): JSON 정수만 받는다.

본문에 id를 받는 요청의 예로 Action 등록의 선택 목록 `{id}`(Action 유형)를 쓴다. 형식 검증이
Deal 조회(404)보다 먼저이므로, 형식이 틀리면 없는 Deal이어도 422다.
"""

from typing import Any

import pytest

from tests.support.ids import MAX_ID
from tests.unit.web.platform_http import KIM, role_clients, then_problem_is

ACTIONS = "/api/v1/deals/20260101-ZZZZ/actions"


def _body(type_id: Any) -> dict[str, Any]:  # noqa: ANN401
    return {"action_type": {"id": type_id}, "action": "진행", "next_action": "", "memo": ""}


@pytest.mark.parametrize(
    "bad_id", ["7", True, 7.5, 0, MAX_ID + 1], ids=["string", "bool", "float", "zero", "too-large"]
)
async def test_a_body_id_that_is_not_a_json_integer_in_range_is_422(bad_id: Any) -> None:  # noqa: ANN401
    """본문 id는 JSON 정수만 받는다.

    테스트 코드: PL-024
    """
    # given: 본문에 id를 받는 요청(선택 목록 {id})을 보내는 KIM
    async with role_clients() as c:
        # when: id에 문자열 "7"·불리언·실수·0·2^53을 넣는다
        response = await c[KIM].post(ACTIONS, json=_body(bad_id))
    # then: 모두 422 request-validation이다
    then_problem_is(response, 422, "request-validation")


async def test_the_largest_body_id_passes_the_format_check() -> None:
    """상한 id(2^53-1)는 형식 검증을 통과해 유스케이스의 404까지 간다(PL-024의 경계).

    테스트 코드: PL-024
    """
    # given: KIM, 없는 Deal
    async with role_clients() as c:
        # when: id에 JSON 정수 상한값을 넣는다
        response = await c[KIM].post(ACTIONS, json=_body(MAX_ID))
    # then: 422가 아니라 없는 Deal의 404 not-found다
    then_problem_is(response, 404, "not-found")
