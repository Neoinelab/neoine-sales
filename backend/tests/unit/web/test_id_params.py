"""정수 id 경로 파라미터(PL-021~PL-023): 1 이상 2^53-1 이하의 정수만 받는다.

대상은 앱 계약(`app.openapi()`)에서 정수 id 경로 파라미터를 가진 모든 (메서드, 경로)다. 정수가 아닌
값·0·음수·상한 초과는 유스케이스까지 가기 전에 422 request-validation이고(500이 아니다), 형식이
맞는 없는 id는 그 경로의 404 not-found다. 호출은 모든 경로를 허용하는 admin(BOSS)이 한다.
"""

from typing import Any

from app.domain.auth.mode import AuthMode
from tests.fakes.use_cases import FakeUseCases
from tests.support.ids import MAX_ID
from tests.support.layout_defs import SIDE_CHART_FIRST
from tests.support.openapi_spec import app_contract, id_path_routes
from tests.support.permission_table import request_body
from tests.unit.web.platform_http import BOSS, role_clients
from tests.unit.web.saved_report_http import create_body

NAME = {"name": "x"}
ACTION = {"action_type": {"name": "미팅"}, "action": "진행", "next_action": "", "memo": ""}
CONTACT = {"company": "네오인", "name": "김철수"}
LICENSE = {"start_date": "2026-11-01", "term_amount": 1, "term_unit": "year"}
MEETING = {"partner_company": "한빛파트너스", "meeting_date": "2026-10-01", "content": "킥오프"}
# 본문 검증이 id 검사(404)보다 먼저이므로, 본문이 있는 경로는 형식이 맞는 최소 본문을 쓴다.
VALID_BODIES: dict[tuple[str, str], dict[str, Any]] = {
    ("PUT", "/api/v1/contacts/{contact_id}"): CONTACT,
    ("PUT", "/api/v1/deal-actions/{action_id}"): ACTION,
    ("PUT", "/api/v1/deal-actions/{action_id}/next-action-status"): {"status": "done"},
    ("PATCH", "/api/v1/codes/{code_id}"): NAME,
    ("PATCH", "/api/v1/bant-labels/{label_id}"): NAME,
    ("PATCH", "/api/v1/action-types/{type_id}"): NAME,
    ("PATCH", "/api/v1/vendors/{vendor_id}"): NAME,
    ("PUT", "/api/v1/partner-meetings/{meeting_id}"): MEETING,
    ("POST", "/api/v1/license-contracts/{contract_id}/issue"): LICENSE,
    ("POST", "/api/v1/license-contracts/{contract_id}/renewal"): LICENSE,
    ("PUT", "/api/v1/reports/{report_id}"): {**create_body(), "revision": 1},
    ("PUT", "/api/v1/reports/{report_id}/layout"): {"layout": SIDE_CHART_FIRST, "revision": 1},
    ("POST", "/api/v1/reports/{report_id}/copy"): {"name": "복사", "visibility": "public"},
    ("PUT", "/api/v1/users/{user_id}/password"): {"password": "Passw0rd-ok"},
    ("PUT", "/api/v1/users/{user_id}/role"): {"role": "sales"},
}
NOT_INTEGERS = ["abc", "1.5", "6f1c1b3a-0000-4000-8000-000000000001", "0x10", "1e3"]
OUT_OF_RANGE = ["0", "-1", str(MAX_ID + 1), "9223372036854775808"]
ROUTES = id_path_routes(app_contract())


def _body(method: str, template: str) -> dict[str, Any] | None:
    return VALID_BODIES.get((method, template), request_body(method))


async def _statuses(values: list[str], *, valid_body: bool) -> dict[str, str]:
    """모든 id 경로를 값마다 불러 기대와 다른 응답만 `경로 값 -> 응답 요약`으로 모은다."""
    wrong: dict[str, str] = {}
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.LOCAL)  # 비밀번호 재설정은 local 모드에서만 열린다
    async with role_clients(use_cases) as c:
        for method, template, names in ROUTES:
            for value in values:
                path = template
                for name in names:
                    path = path.replace("{" + name + "}", value)
                body = _body(method, template) if valid_body else request_body(method)
                response = await c[BOSS].request(method, path, json=body)
                if valid_body:
                    ok = response.status_code == 404 and _kind(response) == "not-found"
                else:
                    ok = response.status_code == 422 and _on_path(response)
                if not ok:
                    wrong[f"{method} {template} = {value}"] = f"{response.status_code}"
    return wrong


def _kind(response: Any) -> str:  # noqa: ANN401
    return str(response.json().get("type", "")).rsplit("/", 1)[-1]


def _on_path(response: Any) -> bool:  # noqa: ANN401
    """request-validation Problem이고 오류 위치에 path 파라미터가 들어 있다."""
    body = response.json()
    if _kind(response) != "request-validation":
        return False
    return any(error["loc"][0] == "path" for error in body["errors"])


def test_the_contract_has_many_id_routes_to_check() -> None:
    """계약에서 뽑은 id 경로가 충분히 있어 아래 전수 검사가 빈 검사가 아니다."""
    # when: 계약의 정수 id 경로를 센다
    count = len(ROUTES)
    # then: 30개 이상이다
    assert count >= 30


async def test_a_non_integer_path_id_is_a_request_validation_error() -> None:
    """정수가 아닌 id 경로 값은 422다.

    테스트 코드: PL-021
    """
    # when: id 자리에 abc·1.5·UUID·0x10·1e3을 넣어 부른다
    #   (전제: id 경로 파라미터를 가진 모든 경로(권한이 있는 admin))
    wrong = await _statuses(NOT_INTEGERS, valid_body=False)
    # then: 모두 path 위치의 422 request-validation이다
    assert wrong == {}


async def test_zero_negative_and_too_large_path_ids_are_rejected_not_500() -> None:
    """0·음수·상한 초과 id 경로 값은 500이 아니라 422다.

    테스트 코드: PL-022
    """
    # when: id 자리에 0·-1·2^53·2^63을 넣는다 (전제: 같은 경로들)
    wrong = await _statuses(OUT_OF_RANGE, valid_body=False)
    # then: 모두 path 위치의 422 request-validation이다
    assert wrong == {}


async def test_the_largest_allowed_path_id_reaches_the_use_case() -> None:
    """상한 id(2^53-1)는 유스케이스까지 가서 404다.

    테스트 코드: PL-023
    """
    # when: id 자리에 9007199254740991을 넣어 형식이 맞는 본문으로 부른다
    #   (전제: 같은 경로들, 그런 id의 대상은 없음)
    wrong = await _statuses([str(MAX_ID)], valid_body=True)
    # then: 422가 아니라 그 경로의 404 not-found다
    assert wrong == {}
