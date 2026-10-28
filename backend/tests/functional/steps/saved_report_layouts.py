"""Reports 결과 배치(layout) feature의 step.

배치는 `{view, order, arrange}`다. 배치만 바꾸는 `PUT /api/v1/reports/{id}/layout`은 응답의
`revision`을 이어 받아 연달아 보낼 수 있다. 읽을 수 없는 저장 값은 API로 만들 수 없어 DB를 직접
바꿔 준비한다.
"""

from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.login_db import sql_rows
from tests.functional.steps.saved_reports import REPORTS, when_get_report

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

DEFAULT_LAYOUT: Final[dict[str, Any]] = {
    "view": "both",
    "order": ["table", "chart"],
    "arrange": "stacked",
}
CHART_FIRST_SIDE: Final[dict[str, Any]] = {
    "view": "chart",
    "order": ["chart", "table"],
    "arrange": "side_by_side",
}
TABLE_ONLY: Final[dict[str, Any]] = {
    "view": "table",
    "order": ["table", "chart"],
    "arrange": "stacked",
}
BOTH_SIDE: Final[dict[str, Any]] = {
    "view": "both",
    "order": ["table", "chart"],
    "arrange": "side_by_side",
}


async def given_stored_layout_is_null(api: Api, report_id: object) -> None:
    """DB에서 그 리포트의 layout 열을 NULL로 되돌렸다(마이그레이션 직후의 기존 행과 같은 상태)."""
    await sql_rows(api, "update reports set layout = null where id = :id", id=int(str(report_id)))


async def when_save_layout(
    api: Api, report_id: object, layout: object, revision: object
) -> Response:
    api.clock.advance(1)
    return await api.request(
        "PUT", f"{REPORTS}/{report_id}/layout", json={"layout": layout, "revision": revision}
    )


async def when_layouts_saved_in_sequence(
    api: Api, report: dict[str, Any], layouts: list[dict[str, Any]]
) -> list[Response]:
    """응답의 revision을 다음 요청에 담아 배치를 차례로 저장한다(화면의 연속 변경과 같다)."""
    responses: list[Response] = []
    revision = report["revision"]
    for layout in layouts:
        response = await when_save_layout(api, report["id"], layout, revision)
        responses.append(response)
        if response.status_code != 200:
            break
        revision = response.json()["revision"]
    return responses


async def then_detail_layout_is(
    api: Api, report_id: object, layout: dict[str, Any], *, revision: int | None = None
) -> None:
    """지금 로그인한 사용자가 다시 읽은 상세의 배치(와 revision)가 기대와 같다."""
    response = await when_get_report(api, report_id)
    assert response.status_code == 200, response.text
    assert response.json()["layout"] == layout
    if revision is not None:
        assert response.json()["revision"] == revision
