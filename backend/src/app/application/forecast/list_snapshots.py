from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.forecast_repository import SnapshotInfo
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class ListForecastSnapshots:
    """저장된 기준 월 목록(최근 순)."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> Sequence[SnapshotInfo]:
        async with self._uow_factory() as uow:
            return await uow.forecast_snapshots.list_periods()
