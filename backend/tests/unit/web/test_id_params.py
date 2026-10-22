"""정수 id 경로 파라미터(AC-13): 1 이상 2^53-1 이하의 정수만 받는다.

정수가 아닌 값·0·음수·상한 초과는 유스케이스까지 가기 전에 422 request-validation이다(500이 아니다).
형식이 맞는 없는 id는 지금처럼 404 not-found다. 대상 경로는 id를 경로로 받는 모든 리소스다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.fakes.use_cases import FakeUseCases
from tests.support.ids import MAX_ID
from tests.unit.web.vendor_http import client_for, problem

if TYPE_CHECKING:
    from collections.abc import Sequence

NAME = {"name": "x"}
ACTION = {"action_type": {"name": "미팅"}, "action": "진행", "next_action": "", "memo": ""}
CONTACT = {"company": "네오인", "name": "김철수"}

# (메서드, 경로 템플릿, 본문). `{}`가 시험할 id 자리다. 나머지 id는 형식이 맞는 값(1)이다.
ROUTES = [
    ("GET", "/api/v1/deal-actions/{}", None),
    ("PUT", "/api/v1/deal-actions/{}", ACTION),
    ("DELETE", "/api/v1/deal-actions/{}", None),
    ("GET", "/api/v1/attachments/{}", None),
    ("GET", "/api/v1/attachments/{}/download", None),
    ("DELETE", "/api/v1/attachments/{}", None),
    ("PATCH", "/api/v1/vendors/{}", NAME),
    ("DELETE", "/api/v1/vendors/{}", None),
    ("PATCH", "/api/v1/action-types/{}", NAME),
    ("DELETE", "/api/v1/action-types/{}", None),
    ("PATCH", "/api/v1/codes/{}", NAME),
    ("DELETE", "/api/v1/codes/{}", None),
    ("PATCH", "/api/v1/bant-labels/{}", NAME),
    ("DELETE", "/api/v1/bant-labels/{}", None),
    ("PUT", "/api/v1/contacts/{}", CONTACT),
    ("DELETE", "/api/v1/contacts/{}", None),
    ("DELETE", "/api/v1/users/{}", None),
]
NOT_INTEGERS = ["abc", "1.5", "6f1c1b3a-0000-4000-8000-000000000001", "0x10", "1e3"]
OUT_OF_RANGE = ["0", "-1", str(MAX_ID + 1), "9223372036854775808"]


def _ids(routes: Sequence[tuple[str, str, object]]) -> list[str]:
    return [f"{method} {template}" for method, template, _ in routes]


@pytest.mark.parametrize("value", NOT_INTEGERS)
@pytest.mark.parametrize(("method", "template", "body"), ROUTES, ids=_ids(ROUTES))
async def test_a_non_integer_path_id_is_a_request_validation_error(
    method: str, template: str, body: object, value: str
) -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.request(method, template.replace("{}", value), json=body)

    problem(response, 422, "request-validation")


@pytest.mark.parametrize("value", OUT_OF_RANGE)
@pytest.mark.parametrize(("method", "template", "body"), ROUTES, ids=_ids(ROUTES))
async def test_zero_negative_and_too_large_path_ids_are_rejected(
    method: str, template: str, body: object, value: str
) -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.request(method, template.replace("{}", value), json=body)

    problem(response, 422, "request-validation")  # 500(BIGINT 범위 초과 등)이 아니다


@pytest.mark.parametrize(("method", "template", "body"), ROUTES, ids=_ids(ROUTES))
async def test_the_largest_allowed_path_id_reaches_the_use_case(
    method: str, template: str, body: object
) -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.request(method, template.replace("{}", str(MAX_ID)), json=body)

    problem(response, 404, "not-found")
