"""단계별 건수와 통화별 매출 합계(파이프라인 현황)."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from app.domain.deal.stage import DealStage

if TYPE_CHECKING:
    from collections.abc import Iterable
    from decimal import Decimal


@dataclass(frozen=True, slots=True)
class StageTotal:
    """저장소 집계 한 줄: (단계, 통화)별 건수와 합계. 합계는 Money 한도를 넘을 수 있다."""

    stage: DealStage
    currency: str
    deal_count: int
    amount: Decimal


@dataclass(frozen=True, slots=True)
class CurrencyAmount:
    currency: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class StageSummary:
    stage: DealStage
    deal_count: int
    totals: tuple[CurrencyAmount, ...]


@dataclass(frozen=True, slots=True)
class DealPipeline:
    """모든 단계를 DealStage 선언 순서로 담는다. 딜이 없는 단계는 0건·합계 없음."""

    stages: tuple[StageSummary, ...]

    @classmethod
    def from_totals(cls, totals: Iterable[StageTotal]) -> Self:
        rows = list(totals)
        summaries = []
        for stage in DealStage:
            mine = sorted((t for t in rows if t.stage is stage), key=lambda t: t.currency)
            summaries.append(
                StageSummary(
                    stage=stage,
                    deal_count=sum(t.deal_count for t in mine),
                    totals=tuple(CurrencyAmount(t.currency, t.amount) for t in mine),
                )
            )
        return cls(stages=tuple(summaries))
