"""저장 리포트 요청·응답 스키마. 규칙(이름·공개 범위·정의)은 도메인이 판단한다."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, Field, StrictInt, StrictStr

from app.application.report.saved_inputs import ReportContentInput, ReportMetaInput
from app.domain.report.chart import ChartKind, LegendPosition
from app.domain.report.raw import RawChart, RawLayout
from app.domain.report.stored import definition_to_json
from app.domain.report.vocabulary import Entity
from app.domain.saved_report.layout import (
    ResultTile,
    ResultView,
    TileArrange,
    layout_to_json,
)
from app.web.schemas.common import RequestModel
from app.web.schemas.report_query import ReportQueryRequest
from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef, ref_of

if TYPE_CHECKING:
    from app.application.report.saved_views import ReportItemView
    from app.domain.saved_report.entities import Report
    from app.domain.user.value_objects import UserId
    from app.domain.user.value_objects import UserRef as DomainUserRef

CHART_PROBLEM = (
    "저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요."
)


class ReportMetaRequest(RequestModel):
    name: StrictStr
    description: StrictStr = ""
    visibility: StrictStr

    def to_meta(self) -> ReportMetaInput:
        return ReportMetaInput(self.name, self.description, self.visibility)


class ReportChartRequest(RequestModel):
    """차트 요청: 모양(필수 키·알 수 없는 키 거부)만 확인하고 값은 원시 그대로 도메인에 넘긴다."""

    kind: Any
    category: Any
    values: Any
    series: Any = None
    swap: Any = False
    title: Any = ""
    legend: Any = "top"
    data_labels: Any = False
    category_axis_title: Any = ""
    value_axis_title: Any = ""
    value_min: Any = None
    value_max: Any = None
    secondary_axis: Any = False

    def to_raw(self) -> RawChart:
        return RawChart(**self.model_dump())


class ReportLayoutRequest(RequestModel):
    """결과 배치 요청: 모양(필수 키·알 수 없는 키 거부)만 확인하고 값은 도메인이 판단한다."""

    view: Any
    order: Any
    arrange: Any

    def to_raw(self) -> RawLayout:
        return RawLayout(**self.model_dump())


class ReportLayoutResponse(BaseModel):
    """저장된 결과 배치. order의 앞이 왼쪽(한 줄) 또는 위(두 줄)다."""

    view: ResultView
    order: Annotated[list[ResultTile], Field(min_length=2, max_length=2)]
    arrange: TileArrange


class ReportChartResponse(BaseModel):
    """저장된(정규화된) 차트. 키가 모두 있다."""

    kind: ChartKind
    category: int
    series: int | None
    values: list[int]
    swap: bool
    title: str
    legend: LegendPosition
    data_labels: bool
    category_axis_title: str
    value_axis_title: str
    value_min: int | float | None
    value_max: int | float | None
    secondary_axis: bool


class ReportCreateRequest(ReportMetaRequest):
    definition: ReportQueryRequest
    chart: ReportChartRequest | None = None
    layout: ReportLayoutRequest | None = None

    def to_input(self) -> ReportContentInput:
        return ReportContentInput(
            self.name,
            self.description,
            self.visibility,
            self.definition.to_raw(),
            self.chart.to_raw() if self.chart else None,
            self.layout.to_raw() if self.layout else None,
        )


class ReportUpdateRequest(ReportCreateRequest):
    revision: Annotated[StrictInt, Field(ge=1)]


class ReportLayoutUpdateRequest(RequestModel):
    layout: ReportLayoutRequest
    revision: Annotated[StrictInt, Field(ge=1)]


class ReportCopyRequest(ReportMetaRequest):
    pass


class ReportSummaryResponse(BaseModel):
    id: int
    name: str
    description: str
    visibility: str
    owner: UserRef
    updated_by: UserRef
    entities: list[Entity]
    created_at: ServerDateTime
    updated_at: ServerDateTime
    chart_kind: ChartKind | None

    @classmethod
    def from_report(
        cls,
        report: Report,
        entities: tuple[Entity, ...],
        refs: Mapping[UserId, DomainUserRef],
    ) -> ReportSummaryResponse:
        return cls(**_summary(report, entities, refs))


class ReportDetailResponse(ReportSummaryResponse):
    revision: int
    definition: ReportQueryRequest
    generated_sql: str
    chart: ReportChartResponse | None
    chart_problem: str | None
    layout: ReportLayoutResponse

    @classmethod
    def from_detail(
        cls, report: Report, refs: Mapping[UserId, DomainUserRef]
    ) -> ReportDetailResponse:
        return cls(
            **_summary(report, report.entities(), refs),
            revision=report.revision,
            definition=ReportQueryRequest.model_validate(
                definition_to_json(report.readable_definition())
            ),
            generated_sql=report.generated_sql,
            chart=_chart(report),
            chart_problem=CHART_PROBLEM if report.chart_unreadable else None,
            layout=ReportLayoutResponse.model_validate(layout_to_json(report.layout)),
        )


def _chart(report: Report) -> ReportChartResponse | None:
    raw = report.chart
    return None if raw is None else ReportChartResponse.model_validate(_fields(raw))


def _fields(raw: RawChart) -> dict[str, object]:
    return {f: getattr(raw, f) for f in RawChart.__dataclass_fields__}


def _summary(
    report: Report, entities: tuple[Entity, ...], refs: Mapping[UserId, DomainUserRef]
) -> dict[str, object]:
    return {
        "id": report.id,
        "name": report.name,
        "description": report.description,
        "visibility": report.visibility.value,
        "owner": ref_of(refs, report.owner_user_id),
        "updated_by": ref_of(refs, report.updated_by_user_id),
        "entities": list(entities),
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "chart_kind": report.chart_kind(),
    }


def report_user_ids(reports: list[Report]) -> set[UserId]:
    return {i for r in reports for i in (r.owner_user_id, r.updated_by_user_id)}


def summaries(
    items: list[ReportItemView], refs: Mapping[UserId, DomainUserRef]
) -> list[ReportSummaryResponse]:
    return [ReportSummaryResponse.from_report(i.report, i.entities, refs) for i in items]
