"""리포트 결과 배치: 보기 방식, 타일 순서, 한 줄/두 줄. 저장·복제되는 표시 설정이다."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from app.domain.report.errors import IssueLog, ReportDefinitionError
from app.domain.report.parse_columns import enum_member

if TYPE_CHECKING:
    from app.domain.report.raw import RawLayout

_ORDER_SIZE = 2


class ResultView(StrEnum):
    BOTH = "both"
    CHART = "chart"
    TABLE = "table"


class ResultTile(StrEnum):
    TABLE = "table"
    CHART = "chart"


class TileArrange(StrEnum):
    SIDE_BY_SIDE = "side_by_side"
    STACKED = "stacked"


@dataclass(frozen=True, slots=True)
class ReportLayout:
    """order의 앞이 왼쪽(한 줄) 또는 위(두 줄)다. 하나만 보여도 order·arrange는 보존한다."""

    view: ResultView
    order: tuple[ResultTile, ResultTile]
    arrange: TileArrange


DEFAULT_LAYOUT: Final = ReportLayout(
    ResultView.BOTH, (ResultTile.TABLE, ResultTile.CHART), TileArrange.STACKED
)


def _parse_order(raw: object) -> tuple[ResultTile, ResultTile] | None:
    if type(raw) is not list or len(raw) != _ORDER_SIZE:
        return None
    first = enum_member(ResultTile, raw[0])
    second = enum_member(ResultTile, raw[1])
    if first is None or second is None or first is second:
        return None
    return (first, second)


def parse_layout(raw: RawLayout) -> ReportLayout:
    """위반을 모두 모아 `ReportDefinitionError`(위치는 `("layout", 항목)`)."""
    log = IssueLog()
    view = enum_member(ResultView, raw.view)
    order = _parse_order(raw.order)
    arrange = enum_member(TileArrange, raw.arrange)
    if view is None:
        log.add(("layout", "view"), "invalid-value", "보기 방식은 both, chart, table 중 하나입니다")
    if order is None:
        log.add(
            ("layout", "order"),
            "invalid-value",
            "타일 순서는 table과 chart를 한 번씩 담아야 합니다",
        )
    if arrange is None:
        log.add(("layout", "arrange"), "invalid-value", "배치는 side_by_side 또는 stacked입니다")
    if log.items or view is None or order is None or arrange is None:
        raise ReportDefinitionError(log.items)
    return ReportLayout(view, order, arrange)


def layout_to_json(layout: ReportLayout) -> dict[str, object]:
    return {
        "view": layout.view.value,
        "order": [tile.value for tile in layout.order],
        "arrange": layout.arrange.value,
    }


def layout_from_json(data: object) -> ReportLayout:
    """저장된 값을 읽는다. NULL·깨진 모양·알 수 없는 값이면 기본 배치(실패하지 않는다)."""
    from app.domain.report.raw import RawLayout  # noqa: PLC0415

    if not isinstance(data, dict):
        return DEFAULT_LAYOUT
    raw = RawLayout(data.get("view"), data.get("order"), data.get("arrange"))
    try:
        return parse_layout(raw)
    except ReportDefinitionError:
        return DEFAULT_LAYOUT
