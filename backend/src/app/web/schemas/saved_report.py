"""저장 리포트 요청·응답 스키마. 규칙(이름·공개 범위·정의)은 도메인이 판단한다."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field, StrictInt, StrictStr

from app.application.report.saved_inputs import ReportContentInput, ReportMetaInput
from app.domain.report.stored import definition_to_json
from app.domain.report.vocabulary import Entity
from app.web.schemas.common import RequestModel
from app.web.schemas.report_query import ReportQueryRequest
from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef, ref_of

if TYPE_CHECKING:
    from app.application.report.saved_views import ReportItemView
    from app.domain.saved_report.entities import Report
    from app.domain.user.value_objects import UserId
    from app.domain.user.value_objects import UserRef as DomainUserRef


class ReportMetaRequest(RequestModel):
    name: StrictStr
    description: StrictStr = ""
    visibility: StrictStr

    def to_meta(self) -> ReportMetaInput:
        return ReportMetaInput(self.name, self.description, self.visibility)


class ReportCreateRequest(ReportMetaRequest):
    definition: ReportQueryRequest

    def to_input(self) -> ReportContentInput:
        return ReportContentInput(
            self.name, self.description, self.visibility, self.definition.to_raw()
        )


class ReportUpdateRequest(ReportCreateRequest):
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
        )


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
    }


def report_user_ids(reports: list[Report]) -> set[UserId]:
    return {i for r in reports for i in (r.owner_user_id, r.updated_by_user_id)}


def summaries(
    items: list[ReportItemView], refs: Mapping[UserId, DomainUserRef]
) -> list[ReportSummaryResponse]:
    return [ReportSummaryResponse.from_report(i.report, i.entities, refs) for i in items]
