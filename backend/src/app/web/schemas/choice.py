"""카탈로그 항목 선택 요청: 있는 항목의 id 또는 찾거나 만들 이름 중 정확히 하나."""

from typing import Self

from pydantic import model_validator

from app.application.choice import CatalogChoice
from app.web.schemas.common import RequestModel
from app.web.schemas.ids import BodyId


class CatalogChoiceRequest(RequestModel):
    id: BodyId | None = None
    name: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.id is None) == (self.name is None):
            raise ValueError("id와 name 중 하나만 보내세요.")
        return self

    def to_choice(self) -> CatalogChoice:
        return CatalogChoice(id=self.id, name=self.name)
