"""코드(Status·Forecast) 요청·응답 스키마. 빈 이름 검사는 도메인이 한다(min_length 금지)."""

from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.domain.code.values import CodeId, CodeKind
from app.web.schemas.common import RequestModel
from app.web.schemas.ids import BodyId

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.code.dto import CodeSet, CodeUsage
    from app.domain.code.entities import Code


class CodeCreateRequest(RequestModel):
    kind: CodeKind
    name: str
    probability_hint: str | None = None


class CodeRenameRequest(RequestModel):
    name: str


class CodeOrderRequest(RequestModel):
    kind: CodeKind
    ordered_ids: list[BodyId]

    def ids(self) -> list[CodeId]:
        return [CodeId(i) for i in self.ordered_ids]


class CodeResponse(BaseModel):
    id: int
    kind: CodeKind
    key: str
    name: str
    order: int
    locked: bool
    outcome: str
    probability_hint: str | None

    @classmethod
    def from_entity(cls, code: Code) -> CodeResponse:
        return cls(
            id=code.id,
            kind=code.kind,
            key=code.key.value,
            name=code.name,
            order=code.order,
            locked=code.locked,
            outcome=code.outcome.value,
            probability_hint=code.probability_hint,
        )


class CodeUsageResponse(CodeResponse):
    usage_count: int

    @classmethod
    def from_usage(cls, item: CodeUsage) -> CodeUsageResponse:
        base = CodeResponse.from_entity(item.code)
        return cls(**base.model_dump(), usage_count=item.usage_count)


class CodeSetResponse(BaseModel):
    statuses: list[CodeResponse]
    forecasts: list[CodeResponse]

    @classmethod
    def from_set(cls, code_set: CodeSet) -> CodeSetResponse:
        return cls(
            statuses=[CodeResponse.from_entity(c) for c in code_set.statuses],
            forecasts=[CodeResponse.from_entity(c) for c in code_set.forecasts],
        )


def usage_responses(items: Sequence[CodeUsage]) -> list[CodeUsageResponse]:
    return [CodeUsageResponse.from_usage(item) for item in items]
