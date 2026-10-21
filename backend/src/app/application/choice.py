"""카탈로그 항목(Action 유형, BANT Label) 선택 입력."""

from dataclasses import dataclass

from app.domain.common.errors import InvalidValueError

CHOICE_EXACTLY_ONE = "id와 name 중 하나만 보내세요."


@dataclass(frozen=True, slots=True)
class CatalogChoice:
    """카탈로그 항목 선택: 있는 항목의 id 또는 찾거나 만들 이름 중 정확히 하나."""

    id: int | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        if (self.id is None) == (self.name is None):
            raise InvalidValueError(CHOICE_EXACTLY_ONE)
