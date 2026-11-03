"""Reports 4단계(차트 저장) feature의 step.

정의는 Vendor와 분기 그룹핑(`VENDOR_QUARTER_BODY`)이다.
컬럼 index: 0 Vendor, 1 분기, 2 금액 합계, 3 건수.
깨진 저장 차트는 API로 만들 수 없으므로 DB의 `reports.chart`를 직접 바꿔 준비한다.
"""

from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.login_db import sql_rows
from tests.functional.steps.reports import VENDOR_QUARTER_BODY
from tests.functional.steps.saved_reports import report_body

if TYPE_CHECKING:
    from tests.functional.conftest import Api

CHART_PROBLEM: Final = (
    "저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요."
)
STACKED_BAR: Final[dict[str, Any]] = {
    "kind": "stacked_bar",
    "category": 0,
    "series": 1,
    "values": [2],
    "swap": False,
    "title": "Vendor별 분기 Pipeline",
    "legend": "top",
    "data_labels": False,
    "category_axis_title": "Vendor",
    "value_axis_title": "금액 (천원)",
    "value_min": None,
    "value_max": None,
    "secondary_axis": False,
    "histogram": None,
    "show_total": False,
    "combo_series": None,
}
COMBO: Final[dict[str, Any]] = {
    **STACKED_BAR,
    "kind": "combo",
    "series": None,
    "values": [2, 3],
    "secondary_axis": True,
    "combo_series": [
        {"type": "column", "secondary": False},
        {"type": "line", "secondary": True},
    ],
}
LEGACY_KEYS: Final = [
    "kind",
    "category",
    "series",
    "values",
    "swap",
    "title",
    "legend",
    "data_labels",
    "category_axis_title",
    "value_axis_title",
    "value_min",
    "value_max",
    "secondary_axis",
]
# 한 그룹(Vendor)과 집계 3개(index 1 금액 합계, 2 사용자 수 합계, 3 건수)
ONE_GROUP_BODY: Final[dict[str, Any]] = {
    "columns": [
        {"field": "deal.vendor", "group": True},
        {"field": "deal.amount", "aggregate": "sum", "label": "금액 합계"},
        {"field": "deal.users", "aggregate": "sum", "label": "사용자 수"},
        {"field": "deal.code", "aggregate": "count", "label": "건수"},
    ],
    "conditions": [],
    "combine": "and",
    "row_limit": 1000,
}
UNGROUPED_BODY: Final[dict[str, Any]] = {
    "columns": [{"field": "deal.code"}, {"field": "deal.amount", "label": "금액"}],
    "conditions": [],
    "combine": "and",
    "row_limit": 1000,
}
AUTO_BINS: Final[dict[str, Any]] = {
    "bin_mode": "auto",
    "bin_count": None,
    "bin_width": None,
    "overflow": None,
    "underflow": None,
}


def new_chart(kind: str, **changes: object) -> dict[str, Any]:
    """기본값을 채운 16개 키 차트."""
    return {**STACKED_BAR, "kind": kind, "series": None, "values": [1], **changes}


def legacy_combo_json(*, secondary_axis: bool) -> str:
    """새 키 3개가 없는 옛 형식 콤보 차트 JSON(값 열 3개)."""
    import json  # noqa: PLC0415

    legacy = {k: v for k, v in COMBO.items() if k in LEGACY_KEYS}
    return json.dumps({**legacy, "values": [1, 2, 3], "secondary_axis": secondary_axis})


def chart_report_body_for(
    name: str, definition: dict[str, Any], chart: object = None
) -> dict[str, Any]:
    """임의 정의와 차트를 담은 저장 본문."""
    return report_body(name, definition=definition, chart=chart)


def chart_report_body(
    name: str = "Vendor별 분기", chart: object = None, **overrides: object
) -> dict[str, Any]:
    """Vendor와 분기 정의와 차트(`chart` 인자, None이면 null)를 담은 저장 본문."""
    return report_body(name, definition=VENDOR_QUARTER_BODY, chart=chart, **overrides)


async def given_stored_chart_is_unreadable(api: Api, report_id: object, raw_json: str) -> None:
    """DB에서 그 리포트의 chart 열을 읽을 수 없는 JSON으로 바꿨다."""
    await sql_rows(
        api,
        "update reports set chart = cast(:chart as jsonb) where id = :id",
        chart=raw_json,
        id=int(str(report_id)),
    )


async def given_stored_chart_json_is(api: Api, report_id: object, raw_json: str) -> None:
    """DB에서 그 리포트의 chart 열을 주어진 JSON(옛 형식 등)으로 바꿨다."""
    await given_stored_chart_is_unreadable(api, report_id, raw_json)
