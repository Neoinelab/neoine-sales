from typing import TYPE_CHECKING

from app.domain.bant.errors import DuplicateLabelNameError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.bant.entities import BantLabel
    from app.domain.bant.values import BantLabelId


def ensure_unique_label_name(
    siblings: Sequence[BantLabel], name: str, self_id: BantLabelId | None = None
) -> None:
    """같은 구분 Label 중 대소문자 무시로 같은 이름이 있으면 DuplicateLabelNameError."""
    lowered = name.lower()
    if any(x.id != self_id and x.name.lower() == lowered for x in siblings):
        raise DuplicateLabelNameError(name)
