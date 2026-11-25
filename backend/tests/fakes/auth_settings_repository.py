"""AuthSettingsRepository Port의 InMemory 구현(Fake). 인증 방식은 단일 행(id=1)이다.

`_items`를 유지해 FakeUnitOfWork의 롤백 스냅숏(deepcopy)에 포함된다.
도메인 모듈은 사용 시점에 가져온다(구현 전에도 이 모듈을 쓰는 다른 테스트가 수집된다).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.auth.mode import AuthMode, AuthSettings

_ROW = 1


class FakeAuthSettingsRepository:
    def __init__(self) -> None:
        self._items: dict[int, AuthSettings] = {}

    async def get(self) -> AuthSettings | None:
        return self._items.get(_ROW)

    async def save(
        self, mode: AuthMode, *, now: datetime, setup_pending: bool = False
    ) -> AuthSettings:
        from app.domain.auth.mode import AuthSettings  # noqa: PLC0415 - 구현 지연 import

        stored = AuthSettings(mode=mode, updated_at=now, setup_pending=setup_pending)
        self._items[_ROW] = stored  # 단일 행 upsert
        return stored
