"""ForecastSnapshotRepository Port의 InMemory 구현(Fake, P6 R2).

기준 월(연, 월)당 스냅숏 하나를 보관한다. `replace`는 같은 기준 월이 있으면 통째로
바꾼다(헤더 시각, 저장 당시의 코드 목록(열), 셀 모두). 열은 order 오름차순으로 돌려준다
(SQL 구현과 같은 계약). FakeUnitOfWork가 롤백 대상에 넣고,
셀의 담당자는 users 연결(퇴사 처리 판정)에 포함한다.

domain/application 모듈은 호출 시점에 가져온다(구현이 없어도 FakeUnitOfWork를 쓰는 다른 테스트의
수집이 막히지 않게).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.forecast_repository import SnapshotInfo
    from app.domain.forecast.snapshot import ForecastSnapshot, YearMonth


class FakeForecastSnapshotRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[int, int], ForecastSnapshot] = {}

    async def lock_period(self, period: YearMonth) -> None:
        """단일 프로세스 Fake라 잠글 것이 없다(직렬화 동작은 검증 대상이 아니다)."""

    async def replace(self, snapshot: ForecastSnapshot) -> None:
        from app.domain.forecast.snapshot import ForecastSnapshot  # noqa: PLC0415

        ordered = sorted(snapshot.columns, key=lambda column: column.order)
        self._items[(snapshot.period.year, snapshot.period.month)] = ForecastSnapshot(
            period=snapshot.period,
            taken_at=snapshot.taken_at,
            columns=ordered,
            cells=list(snapshot.cells),
        )

    async def get(self, period: YearMonth) -> ForecastSnapshot | None:
        return self._items.get((period.year, period.month))

    async def list_periods(self) -> Sequence[SnapshotInfo]:
        from app.application.ports.forecast_repository import SnapshotInfo  # noqa: PLC0415

        newest_first = sorted(self._items.items(), key=lambda item: item[0], reverse=True)
        return [SnapshotInfo(period=s.period, taken_at=s.taken_at) for _, s in newest_first]
