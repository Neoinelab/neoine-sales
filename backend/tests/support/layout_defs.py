"""Reports 결과 배치(layout) 테스트용 조립 도우미.

도메인 모듈은 사용 시점에 가져온다(구현 전에도 이 모듈을 쓰는 다른 테스트의 수집이 막히지 않게).

계약(구현 담당이 맞춘다)
- `RawLayout`(`app.domain.report.raw`)은 frozen dataclass이고 `view`·`order`·`arrange`를 키워드로
  만든다. 값은 JSON에서 온 그대로(`object`)이며 `order`는 **list**다.
- `ReportLayout`(`app.domain.saved_report.layout`)은 frozen dataclass이고 `view: ResultView`,
  `order: tuple[ResultTile, ResultTile]`, `arrange: TileArrange`다(모두 StrEnum/tuple).
- `layout_to_json`은 `{"view": str, "order": [str, str], "arrange": str}`를 돌려준다.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domain.saved_report.layout import ReportLayout

    from app.domain.report.raw import RawLayout


def raw_layout(
    view: object = "both",
    order: object = ("table", "chart"),
    arrange: object = "stacked",
) -> RawLayout:
    """원시 배치. order가 튜플이면 JSON처럼 list로 바꿔 담는다(그 외 값은 그대로)."""
    from app.domain.report.raw import RawLayout  # noqa: PLC0415

    return RawLayout(
        view=view,
        order=list(order) if isinstance(order, tuple) else order,
        arrange=arrange,
    )


def make_layout(
    view: str = "both",
    order: tuple[str, str] = ("table", "chart"),
    arrange: str = "stacked",
) -> ReportLayout:
    """유효한 ReportLayout(문자열로 지정)."""
    from app.domain.saved_report.layout import (  # noqa: PLC0415
        ReportLayout,
        ResultTile,
        ResultView,
        TileArrange,
    )

    return ReportLayout(
        view=ResultView(view),
        order=(ResultTile(order[0]), ResultTile(order[1])),
        arrange=TileArrange(arrange),
    )


def layout_json(
    view: str = "both",
    order: tuple[str, str] = ("table", "chart"),
    arrange: str = "stacked",
) -> dict[str, Any]:
    """API·DB JSON 모양의 배치."""
    return {"view": view, "order": list(order), "arrange": arrange}


SIDE_CHART_FIRST = layout_json("chart", ("chart", "table"), "side_by_side")
