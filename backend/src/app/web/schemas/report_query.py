"""Reports 조회 요청·응답 스키마. 값의 허용 여부(필드·연산자·한도)는 도메인이 판단한다.

요청은 JSON 모양만 확인하고(필수 키, 알 수 없는 키 거부) 값은 원시 그대로 도메인에 넘긴다.
그래서 값 위반은 모양 오류(request-validation)가 아니라 위반 목록이 있는 invalid-report로 나온다.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

from app.domain.common.business_date import business_time
from app.domain.report.definition import ActionFilter, RowScope
from app.domain.report.raw import RawColumn, RawCondition, RawReportDefinition, RawSort
from app.domain.report.vocabulary import Aggregate, Entity, FieldType, Format, ResultValueType
from app.web.schemas.common import RequestModel

if TYPE_CHECKING:
    from app.application.report.views import ReportColumnView, ReportResultView

type ResultCell = str | int | float | None


class ReportColumnRequest(RequestModel):
    field: StrictStr
    label: StrictStr | None = None
    format: StrictStr | None = None
    prefix_length: Any = None
    group: StrictBool = False
    aggregate: StrictStr | None = None


class ReportConditionRequest(RequestModel):
    field: StrictStr
    operator: StrictStr
    value: Any = None


class ReportSortRequest(RequestModel):
    column: Any
    direction: Any = "asc"


class ReportQueryRequest(RequestModel):
    columns: list[ReportColumnRequest]
    conditions: list[ReportConditionRequest] = Field(default_factory=list)
    combine: Any = "and"
    sort: ReportSortRequest | None = None
    row_limit: Any = 1000

    def to_raw(self) -> RawReportDefinition:
        return RawReportDefinition(
            columns=tuple(RawColumn(**c.model_dump()) for c in self.columns),
            conditions=tuple(RawCondition(**c.model_dump()) for c in self.conditions),
            combine=self.combine,
            sort=RawSort(**self.sort.model_dump()) if self.sort else None,
            row_limit=self.row_limit,
        )


class ReportResultColumn(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    index: int
    field: str
    label: str
    entity: Entity
    type: FieldType
    value_type: ResultValueType
    format: Format
    prefix_length: int | None
    group: bool
    aggregate: Aggregate | None

    @classmethod
    def from_view(cls, view: ReportColumnView) -> ReportResultColumn:
        return cls.model_validate(view)


class ReportQueryResponse(BaseModel):
    row_scope: RowScope
    action_filter: ActionFilter
    deal_numbers_once: bool
    columns: list[ReportResultColumn]
    rows: list[list[ResultCell]]
    totals: list[ResultCell] | None
    total_count: int
    truncated: bool
    row_limit: int
    sql: str
    elapsed_ms: int
    today: date

    @classmethod
    def from_view(cls, view: ReportResultView) -> ReportQueryResponse:
        return cls(
            row_scope=view.row_scope,
            action_filter=view.action_filter,
            deal_numbers_once=view.deal_numbers_once,
            columns=[ReportResultColumn.from_view(c) for c in view.columns],
            rows=[_cells(row) for row in view.rows],
            totals=_cells(view.totals) if view.totals is not None else None,
            total_count=view.total_count,
            truncated=view.truncated,
            row_limit=view.row_limit,
            sql=view.sql,
            elapsed_ms=view.elapsed_ms,
            today=view.today,
        )


def _cells(row: tuple[Any, ...]) -> list[ResultCell]:
    return [_cell(value) for value in row]


def _cell(value: date | datetime | str | float | None) -> ResultCell:
    """시각은 서버 OS 로컬 오프셋(ServerDateTime 규약)의 ISO 문자열, 날짜는 ISO 날짜로 바꾼다."""
    if isinstance(value, datetime):
        return business_time(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value
