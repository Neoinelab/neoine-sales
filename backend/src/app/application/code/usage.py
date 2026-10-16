from typing import TYPE_CHECKING

from app.domain.code.values import CodeKind

if TYPE_CHECKING:
    from collections.abc import Mapping

    from app.application.ports.unit_of_work import UnitOfWork


async def usage_by_key(uow: UnitOfWork, kind: CodeKind) -> Mapping[str, int]:
    """종류별 key -> 사용하는 Deal 수. Status는 Status 연결, Forecast는 Forecast 연결 기준이다."""
    if kind is CodeKind.STATUS:
        return await uow.deals.count_by_status()
    return await uow.deals.count_by_forecast()
