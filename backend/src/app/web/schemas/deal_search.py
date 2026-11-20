"""Deal 목록 검색·내보내기 쿼리 파라미터. 조건 키는 같고 내보내기에는 페이지 키가 없다."""

from datetime import date
from typing import Annotated, Any

from pydantic import Field, field_validator

from app.application.ports.deal_action_repository import NextActionStatusFilter
from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
from app.application.ports.deal_repository import (
    DEFAULT_PAGE_SIZE,
    KEYWORD_MAX,
    DealQuery,
    DealSort,
    SortOrder,
)
from app.application.ports.pagination import MAX_LIMIT
from app.domain.deal.owner_name import OWNER_NAME_MAX
from app.domain.deal.values import PRODUCT_MAX
from app.domain.user.value_objects import UserId
from app.web.schemas.common import RequestModel
from app.web.schemas.ids import QueryId
from app.web.schemas.period_params import QuartersParam, quarter_set

__all__ = ["DealExportParams", "DealSearchParams"]

STATUS_KEY_MAX = 50
FORECAST_KEYS_MAX = 100


def _document_product_max(schema: dict[str, Any]) -> None:
    """검증은 트림 후 길이로 하므로 maxLength를 검증기가 아닌 문서에만 표기한다."""
    for branch in schema.get("anyOf", [schema]):
        if branch.get("type") == "string":
            branch["maxLength"] = PRODUCT_MAX


ForecastKeyParam = Annotated[str, Field(max_length=STATUS_KEY_MAX)]


class DealExportParams(RequestModel):
    """Deal 조건 쿼리 파라미터. 기간은 양끝을 포함한다. mine=true가 owner_user_id보다 우선."""

    keyword: Annotated[str | None, Field(max_length=KEYWORD_MAX)] = None
    owner_user_id: QueryId | None = None
    owner_name: Annotated[str | None, Field(max_length=OWNER_NAME_MAX)] = None
    mine: bool = False
    vendor_id: QueryId | None = None
    product: Annotated[str | None, Field(json_schema_extra=_document_product_max)] = None
    status_key: Annotated[str | None, Field(max_length=STATUS_KEY_MAX)] = None
    forecast_key: Annotated[list[ForecastKeyParam], Field(max_length=FORECAST_KEYS_MAX)] | None = (
        None
    )
    forecast_outcome: ForecastOutcomeFilter | None = None
    year: Annotated[int | None, Field(ge=1900, le=9999)] = None
    quarter: QuartersParam = None
    month: Annotated[int | None, Field(ge=1, le=12)] = None
    updated_from: date | None = None
    updated_to: date | None = None
    overdue: bool = False
    stale: bool = False
    next_action_status: NextActionStatusFilter | None = None
    sort: DealSort = DealSort.LAST_UPDATED_AT
    order: SortOrder = SortOrder.DESC

    @field_validator("product")
    @classmethod
    def _product_trimmed_length(cls, value: str | None) -> str | None:
        """길이는 앞뒤 공백 제거 후 기준으로 검사한다(트림 전 max_length 금지)."""
        if value is not None and len(value.strip()) > PRODUCT_MAX:
            raise ValueError(f"product는 {PRODUCT_MAX}자 이내로 입력하세요.")
        return value

    def _owner(self) -> UserId | None:
        return None if self.owner_user_id is None else UserId(self.owner_user_id)

    def to_query(self, viewer_user_id: UserId) -> DealQuery:
        criteria = self.model_dump(
            exclude={"mine", "owner_user_id", "owner_name", "forecast_key", "quarter"}
        )
        return DealQuery(
            owner_user_id=viewer_user_id if self.mine else self._owner(),
            forecast_keys=frozenset(self.forecast_key) if self.forecast_key else None,
            owner_name=None if self.mine else self.owner_name,
            quarters=quarter_set(self.quarter),
            **criteria,
        )


class DealSearchParams(DealExportParams):
    """Deal 목록 검색 쿼리 파라미터(조건 + 페이지)."""

    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_PAGE_SIZE
