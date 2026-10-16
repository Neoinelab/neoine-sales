from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.bant.entities import BantLabel


@dataclass(frozen=True, slots=True)
class LabelUsage:
    """Label과 그 Label을 쓰는 Deal 수."""

    label: BantLabel
    usage_count: int
