"""Reports 3단계(저장·목록·열기·편집) feature의 step.

Given은 공개 API로 사용자(역할별)·리포트를 만들고, When은 저장 리포트 API 하나를 호출하며,
Then은 응답과 읽기 API로 본 상태만 단언한다. 여러 사용자는 `given_users`로 등록한 뒤
`given_logged_in`으로 바꿔 로그인한다(등록하려고 admin이 로그인한 상태가 된다).
"""

import json
from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.auth import ADMIN_LOGIN, RoleName, given_user_registered
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.login_db import sql_rows
from tests.functional.steps.users import log_in
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

REPORTS: Final = "/api/v1/reports"
QUERY: Final = f"{REPORTS}/query"
NOT_FOUND_DETAIL: Final = "리포트를 찾을 수 없습니다."
SIMPLE_DEFINITION: Final[dict[str, Any]] = {
    "columns": [{"field": "deal.code"}, {"field": "deal.amount"}],
    "row_limit": 100,
}
OTHER_DEFINITION: Final[dict[str, Any]] = {
    "columns": [{"field": "deal.vendor", "group": True}, {"field": "deal.amount"}],
    "row_limit": 100,
}


def report_body(name: str = "분기 Pipeline", **overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    return {
        "name": name,
        "description": "",
        "visibility": "public",
        "definition": SIMPLE_DEFINITION,
        **overrides,
    }


# --------------------------------------------------------------------------- Given


async def given_users(api: Api, **roles: RoleName) -> None:
    """admin이 사용자들을 등록해 두었다(로그인 아이디=키워드 이름). admin 로그인 상태."""
    for login_id, role in roles.items():
        await given_user_registered(api, login_id=login_id, role=role)


async def given_logged_in(api: Api, login_id: str) -> None:
    """등록된 사용자(또는 root)로 로그인해 있다."""
    await log_in(api, login_id)


async def given_logged_in_as_admin(api: Api) -> None:
    await log_in(api, ADMIN_LOGIN)


async def given_saved_report(
    api: Api,
    name: str = "분기 Pipeline",
    **overrides: Any,  # noqa: ANN401
) -> dict[str, Any]:
    """로그인한 사용자가 리포트를 저장해 두었다(201). 상세 본문을 돌려준다. 시계는 1초 흐른다."""
    api.clock.advance(1)
    response = await api.post(REPORTS, json=report_body(name, **overrides))
    assert response.status_code == 201, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json())


async def given_report_overwritten(
    api: Api,
    report: dict[str, Any],
    name: str,
    **overrides: Any,  # noqa: ANN401
) -> dict[str, Any]:
    """로그인한 사용자가 현재 revision으로 리포트를 덮어썼다(200). 새 상세 본문을 돌려준다."""
    api.clock.advance(1)
    body = {**report_body(name, **overrides), "revision": report["revision"]}
    response = await api.request("PUT", f"{REPORTS}/{report['id']}", json=body)
    assert response.status_code == 200, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json())


async def given_query_body(api: Api, definition: dict[str, Any]) -> dict[str, Any]:
    """정의를 임시 조회(/query)한 응답 본문(저장 리포트 실행과 비교할 기준)."""
    response = await api.post(QUERY, json=definition)
    assert response.status_code == 200, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json())


async def given_stored_definition_uses_legacy_formats(
    api: Api, report_id: object, definition: dict[str, Any]
) -> None:
    """DB에서 그 리포트의 정의 JSON을 예전 포맷(as_is·name·key·prefix)으로 바꿨다.

    API는 예전 포맷을 받지 않으므로 이전 버전이 저장해 둔 상태를 DB로 직접 만든다.
    """
    await sql_rows(
        api,
        "update reports set definition = cast(:definition as jsonb) where id = :id",
        definition=json.dumps(definition),
        id=int(str(report_id)),
    )


# --------------------------------------------------------------------------- When


async def when_save_report(api: Api, body: object) -> Response:
    api.clock.advance(1)
    return await api.post(REPORTS, json=body)


async def when_list_reports(api: Api) -> Response:
    return await api.get(REPORTS)


async def when_get_report(api: Api, report_id: object) -> Response:
    return await api.get(f"{REPORTS}/{report_id}")


async def when_update_report(api: Api, report_id: object, body: object) -> Response:
    api.clock.advance(1)
    return await api.request("PUT", f"{REPORTS}/{report_id}", json=body)


async def when_delete_report(api: Api, report_id: object) -> Response:
    return await api.request("DELETE", f"{REPORTS}/{report_id}")


async def when_copy_report(api: Api, report_id: object, body: object) -> Response:
    api.clock.advance(1)
    return await api.post(f"{REPORTS}/{report_id}/copy", json=body)


async def when_run_saved_report(api: Api, report_id: object) -> Response:
    return await api.post(f"{REPORTS}/{report_id}/run")


async def when_touch_report(
    api: Api, method: str, report_id: object, name: str = "침입"
) -> Response:
    """method에 맞는 본문으로 리포트 하나를 건드린다(GET·PUT·DELETE·copy·run)."""
    path = f"{REPORTS}/{report_id}"
    if method == "GET":
        return await api.get(path)
    if method == "PUT":
        return await api.request("PUT", path, json={**report_body(name), "revision": 1})
    if method == "DELETE":
        return await api.request("DELETE", path)
    if method == "COPY":
        return await api.post(f"{path}/copy", json={"name": name, "visibility": "public"})
    assert method == "RUN", method
    return await api.post(f"{path}/run")


# --------------------------------------------------------------------------- Then


def then_report_is_not_found(response: Response) -> None:
    """없는 id와 같은 404 not-found이고 문구도 같다(존재 여부를 드러내지 않는다)."""
    then_problem_is(response, status=404, type_suffix="not-found")
    assert response.json()["detail"] == NOT_FOUND_DETAIL


async def then_hidden_looks_like_missing(api: Api, response: Response, method: str) -> None:
    """숨겨진 리포트의 응답이 존재하지 않는 id의 응답과 같은 상태·type·문구다."""
    missing = await when_touch_report(api, method, MISSING_ID)
    assert (response.status_code, response.json()["type"], response.json()["detail"]) == (
        missing.status_code,
        missing.json()["type"],
        missing.json()["detail"],
    )


def then_listed_ids_are(response: Response, expected: list[object]) -> None:
    then_status_is(response, 200)
    assert [item["id"] for item in response.json()] == expected


def then_run_matches_query(response: Response, query: dict[str, Any]) -> None:
    then_status_is(response, 200)
    body = response.json()
    assert body["rows"] == query["rows"]
    assert body["totals"] == query["totals"]
    assert body["total_count"] == query["total_count"]
    assert body["columns"] == query["columns"]


async def then_report_equals(api: Api, report_id: object, expected: dict[str, Any]) -> None:
    """지금 로그인한 사용자가 읽은 리포트 상세가 expected와 같다."""
    response = await when_get_report(api, report_id)
    then_status_is(response, 200)
    assert response.json() == expected
