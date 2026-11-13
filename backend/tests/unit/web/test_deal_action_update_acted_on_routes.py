"""PUT /deal-actions/{id}의 acted_on: 형식 오류는 request-validation, 범위 오류는 invalid-value.

유스케이스의 범위 판정 규칙은 `application/test_update_deal_action_acted_on.py`가 맡고,
여기서는 HTTP 오류 type과 거절 시 Action이 그대로인지를 본다.
"""

from typing import Any, Final

import pytest

from app.domain.auth.principal import Role
from tests.unit.web.saved_report_http import clients, problem
from tests.unit.web.test_deal_action_routes import (
    BODY,
    SINGLE,
    _register,
    _use_cases_with_deal,
)

USERS: Final = {"kim": Role.SALES}


@pytest.mark.parametrize("bad", ["2026-13-01", "2026-11-10T10:00:00+09:00", 20261110, ""])
async def test_put_with_a_malformed_acted_on_is_a_request_validation_error(bad: Any) -> None:  # noqa: ANN401
    """형식이 틀린 acted_on으로 수정하면 422 request-validation이고 Action은 그대로다.

    테스트 코드: AC-124
    """
    # given: KIM이 남긴 Action
    use_cases = await _use_cases_with_deal()
    async with clients(use_cases, USERS) as c:
        created = await _register(c["kim"])
        # given: 올바른 형식의 acted_on(지금과 같은 날짜)은 받는다
        accepted = await c["kim"].put(
            f"{SINGLE}/{created['id']}", json={**BODY, "acted_on": created["acted_on"]}
        )
        assert accepted.status_code == 200, accepted.text

        # when: 형식이 틀린 acted_on과 바뀐 내용으로 수정한다
        response = await c["kim"].put(
            f"{SINGLE}/{created['id']}", json={**BODY, "action": "바뀜", "acted_on": bad}
        )
        stored = await c["kim"].get(f"{SINGLE}/{created['id']}")

    # then: 422 request-validation이고 Action은 그대로다
    body = problem(response, 422, "request-validation")
    assert [error["loc"][-1] for error in body["errors"]] == ["acted_on"]
    assert stored.json() == created


async def test_put_with_a_future_acted_on_is_an_invalid_value_error() -> None:
    """오늘 이후 acted_on으로 수정하면 422 invalid-value이고 Action은 그대로다.

    테스트 코드: AC-121
    """
    # given: KIM이 남긴 Action
    use_cases = await _use_cases_with_deal()
    async with clients(use_cases, USERS) as c:
        created = await _register(c["kim"])

        # when: 먼 미래 날짜 acted_on으로 수정한다
        response = await c["kim"].put(
            f"{SINGLE}/{created['id']}", json={**BODY, "acted_on": "2099-01-01"}
        )
        stored = await c["kim"].get(f"{SINGLE}/{created['id']}")

    # then: 422 invalid-value와 수행일 문구이고 Action은 그대로다
    body = problem(response, 422, "invalid-value")
    assert body["detail"] == "수행일은 오늘 이후로 지정할 수 없습니다."
    assert stored.json() == created
