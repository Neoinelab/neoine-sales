from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.bant.entities import BantLabel
    from app.domain.bant.values import BantCategory, BantLabelId


class BantLabelRepository(Protocol):
    """BANT Label 저장소 계약. 이름은 구분 안에서 대소문자 무시로 고유하다."""

    async def list(
        self, category: BantCategory | None = None, *, for_update: bool = False
    ) -> Sequence[BantLabel]:
        """구분 선언 순. 구분 안에서는 기본 Label(default_order) 먼저,
        직접 만든 것은 소문자 이름·id 순.

        for_update=True면 트랜잭션이 끝날 때까지 조회된 구분의 행을 잠근다.
        """
        ...

    async def get(self, label_id: BantLabelId) -> BantLabel:
        """없으면 BantLabelNotFoundError."""
        ...

    async def add(self, label: BantLabel) -> None:
        """같은 구분에 같은 이름(대소문자 무시)이면 DuplicateLabelNameError."""
        ...

    async def update(self, label: BantLabel) -> None:
        """없으면 BantLabelNotFoundError, 이름이 겹치면 DuplicateLabelNameError."""
        ...

    async def delete(self, label_id: BantLabelId) -> None:
        """물리 삭제한다. 없으면 BantLabelNotFoundError."""
        ...
