from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime

    from app.domain.forecast.period import ForecastPeriod
    from app.domain.forecast.summary import ForecastColumn, Tally
    from app.domain.user.value_objects import UserRef


class SummaryBasis(StrEnum):
    LIVE = "live"
    SNAPSHOT = "snapshot"


@dataclass(frozen=True, slots=True)
class ForecastRowView:
    owner: UserRef | None  # 합계 행은 None
    cells: Mapping[str, Tally]
    open_total: Tally


@dataclass(frozen=True, slots=True)
class ForecastSummaryView:
    basis: SummaryBasis
    as_of: datetime
    snapshot_period: str | None  # R2에서 YearMonth로 바뀔 수 있음. R1은 항상 None
    period: ForecastPeriod
    columns: Sequence[ForecastColumn]
    rows: Sequence[ForecastRowView]
    total: ForecastRowView
