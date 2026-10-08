"""파이프라인 값 객체 조립: 8개 단계 고정 순서, 빈 단계 0건, 통화 정렬, 건수 합산."""

from decimal import Decimal

from app.domain.deal.pipeline import CurrencyAmount, DealPipeline, StageTotal
from app.domain.deal.stage import DealStage


def test_pipeline_lists_all_eight_stages_in_order_with_zero_for_empty() -> None:
    pipeline = DealPipeline.from_totals([])

    assert [s.stage for s in pipeline.stages] == list(DealStage)
    assert len(pipeline.stages) == 8
    assert all(s.deal_count == 0 and s.totals == () for s in pipeline.stages)


def test_totals_are_grouped_per_currency_sorted_and_counts_are_summed() -> None:
    pipeline = DealPipeline.from_totals(
        [
            StageTotal(DealStage.PRICE_NEGOTIATION, "USD", 1, Decimal("5.5")),
            StageTotal(DealStage.PRICE_NEGOTIATION, "KRW", 2, Decimal("100")),
        ]
    )

    summary = next(s for s in pipeline.stages if s.stage is DealStage.PRICE_NEGOTIATION)
    assert summary.deal_count == 3
    assert summary.totals == (
        CurrencyAmount("KRW", Decimal("100")),
        CurrencyAmount("USD", Decimal("5.5")),
    )


def test_input_order_does_not_change_the_result() -> None:
    rows = [
        StageTotal(DealStage.LOST, "USD", 1, Decimal("1")),
        StageTotal(DealStage.PROSPECTING, "KRW", 4, Decimal("40")),
        StageTotal(DealStage.LOST, "EUR", 2, Decimal("2")),
    ]

    forward = DealPipeline.from_totals(rows)
    backward = DealPipeline.from_totals(reversed(rows))

    assert forward == backward
    assert [t.currency for t in forward.stages[-1].totals] == ["EUR", "USD"]


def test_other_stages_stay_empty_when_only_one_stage_has_deals() -> None:
    pipeline = DealPipeline.from_totals([StageTotal(DealStage.LOST, "KRW", 1, Decimal("7"))])

    counts = {s.stage: s.deal_count for s in pipeline.stages}
    assert counts[DealStage.LOST] == 1
    assert sum(counts.values()) == 1


def test_sum_beyond_money_limit_is_kept_as_is() -> None:
    big = Decimal("9999999999999999.9999")  # 16자리 한도 값 두 건의 합
    pipeline = DealPipeline.from_totals([StageTotal(DealStage.PROSPECTING, "KRW", 2, big + big)])

    assert pipeline.stages[0].totals[0].amount == big + big
